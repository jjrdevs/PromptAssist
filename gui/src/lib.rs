use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::Mutex;

use serde::{Deserialize, Serialize};
use tauri::{
    Manager, State,
    tray::{TrayIcon, TrayIconBuilder},
    menu, Menu, MenuItem, PredefinedMenuItem,
};
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

mod cli;
mod shortcuts;

pub const STAGES: [str; 6] = ["research", "plan", "check-plan", "build", "continue", "review-code"];
pub const STAGE_NAMES: [str; 6] = ["Research", "Plan", "Check plan", "Build", "Continue", "Review code"];

/// Where `passist` stores user state. Mirrors the Python CLI:
///   - Windows: `%LOCALAPPDATA%\PromptAssist`
///   - Linux/macOS: `$XDG_CONFIG_HOME/promptassist` (or `~/.config/promptassist`)
///   - Override: env var `PROMPTASSIST_DATA_DIR`.
pub fn data_dir() -> PathBuf {
    if let Some(d) = std::env::var_os("PROMPTASSIST_DATA_DIR") {
        return PathBuf::from(d);
    }
    if let Ok(local) = std::env::var("LOCALAPPDATA") {
        return PathBuf::from(local).join("PromptAssist");
    }
    if let Ok(xdg) = std::env::var("XDG_CONFIG_HOME") {
        return PathBuf::from(xdg).join("promptassist");
    }
    if let Ok(home) = std::env::var("HOME") {
        return PathBuf::from(home).join(".config").join("promptassist");
    }
    PathBuf::from(".").join("promptassist-data")
}

/// Resolve the `passist` executable.
///   - Prefer `PROMPTASSIST_BIN` env var (explicit).
///   - Else look for `.venv/bin/passist` next to the binary or CWD.
///   - Else `passist` on PATH.
pub fn passist_bin() -> String {
    if let Ok(p) = std::env::var("PROMPTASSIST_BIN") {
        return p;
    }
    let mut bases = vec![std::env::current_dir().unwrap_or_else(|_| PathBuf::from("."))];
    if let Ok(exe) = std::env::current_exe() {
        if let Some(parent) = exe.parent() {
            bases.push(parent.to_path_buf());
            if let Some(gp) = parent.parent() {
                bases.push(gp.to_path_buf());
            }
        }
    }
    bases.push(PathBuf::from("/home/jjrdev/workspace/PromptAssist"));
    for base in &bases {
        // 1) One-file CLI dropped next to the GUI binary (the shared-folder layout).
        let candidate = base.join("passist.exe");
        if candidate.is_file() {
            return candidate.to_string_lossy().into_owned();
        }
        let candidate = base.join("passist");
        if candidate.is_file() {
            return candidate.to_string_lossy().into_owned();
        }
        // 2) A venv / Scripts next to the binary (dev / pip install layout).
        for sub in [".venv/bin/passist", "Scripts/passist.exe", ".venv/Scripts/passist.exe"] {
            let candidate = base.join(sub);
            if candidate.is_file() {
                return candidate.to_string_lossy().into_owned();
            }
        }
    }
    "passist".to_string()
}

/// In-memory state shared between commands.
pub struct App {
    /// Most-recently rendered stage text. Used by the auto-paste path.
    last_render: Mutex<Option<String>>,
    /// Feature we're currently operating on (set by the frontend's picker).
    active_feature: Mutex<Option<String>>,
}

// =========================== Tauri commands (frontend → Rust) =============

#[tauri::command]
async fn list_stage_ids() -> Vec<serde_json::Value> {
    (0..STAGES.len())
        .map(|i| serde_json::json!({ "id": STAGES[i], "name": STAGE_NAMES[i] }))
        .collect()
}

#[derive(Serialize)]
struct ApiFeature {
    name: String,
    target_repo: String,
    created: String,
    last_fired_stage: Option<String>,
    total_fires: u32,
    active: bool,
}

#[tauri::command]
async fn list_features(app: tauri::AppHandle) -> Result<Vec<ApiFeature>, String> {
    let raw = cli::run_cli(vec!["ls".into(), "--json".into()]).await?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let active = match app.state::<App>().active_feature.lock().ok() {
        Ok(g) => g.clone(),
        Err(_) => None,
    };
    let out: Vec<ApiFeature> = v
        .get("features")
        .and_then(|a| a.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|f| {
            let name = f.get("name")?.as_str()?.to_string();
            Some(ApiFeature {
                active: active.as_deref() == Some(name.as_str()),
                name,
                target_repo: f.get("target_repo")?.as_str().unwrap_or_default().into(),
                created: f.get("created")?.as_str().unwrap_or_default().into(),
                last_fired_stage: f.get("last_fired_stage").and_then(|s| s.as_str()).map(|s| s.to_string()),
                total_fires: f.get("total_fires").and_then(|n| n.as_u64()).unwrap_or(0) as u32,
            })
        })
        .collect();
    Ok(out)
}

#[tauri::command]
async fn set_active_feature(app: tauri::AppHandle, name: Option<String>) -> Result<bool, String> {
    if let Ok(mut g) = app.state::<App>().active_feature.lock() {
        *g = name;
    }
    Ok(true)
}

#[tauri::command]
async fn new_feature(name: String, target_repo: String) -> Result<ApiFeature, String> {
    let raw = cli::run_cli(vec![
        "new".into(),
        name.clone(),
        "--target".into(),
        target_repo.clone(),
        "--json".into(),
    ]).await?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    Ok(ApiFeature {
        name,
        target_repo,
        created: v.get("created").and_then(|s| s.as_str()).unwrap_or_default().into(),
        last_fired_stage: None,
        total_fires: 0,
        active: true,
    })
}

#[tauri::command]
async fn render_stage(
    app: tauri::AppHandle,
    stage: String,
    feature: Option<String>,
    agent_name: Option<String>,
) -> Result<serde_json::Value, String> {
    let name_arg = match feature {
        Some(f) if !f.is_empty() && f != "-" => f,
        _ => "-".into(),
    };
    let mut args = vec!["run".into(), stage.clone(), name_arg, "--json".into()];
    if let Some(a) = agent_name {
        if !a.is_empty() {
            args.push("--agent-name".into());
            args.push(a);
        }
    }
    let raw = cli::run_cli(args).await?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    if let Ok(mut g) = app.state::<App>().last_render.lock() {
        if let Some(text) = v.get("text").and_then(|t| t.as_str()) {
            *g = Some(text.to_string());
        }
    }
    Ok(v)
}

#[tauri::command]
async fn render_all(app: tauri::AppHandle, feature: Option<String>, agent_name: Option<String>) -> Result<serde_json::Value, String> {
    let name_arg = match feature {
        Some(f) if !f.is_empty() && f != "-" => f,
        _ => "-".into(),
    };
    let mut args = vec!["export".into(), name_arg, "--json".into()];
    if let Some(a) = agent_name {
        if !a.is_empty() {
            args.push("--agent-name".into());
            args.push(a);
        }
    }
    let raw = cli::run_cli(args).await?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let _ = app;
    Ok(v)
}

#[tauri::command]
async fn sync_agent(target_repo: Option<String>, tools: Option<String>) -> Result<Vec<String>, String> {
    let mut args = vec!["sync-agent".into(), "--json".into()];
    if let Some(t) = target_repo {
        if !t.is_empty() {
            args.push("--target".into());
            args.push(t);
        }
    }
    if let Some(t) = tools {
        if !t.is_empty() {
            args.push("--tools".into());
            args.push(t);
        }
    }
    let raw = cli::run_cli(args).await?;
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    Ok(v.get("written")
        .and_then(|a| a.as_array())
        .cloned()
        .unwrap_or_default()
        .into_iter()
        .filter_map(|x| x.as_str().map(|s| s.to_string()))
        .collect())
}

#[derive(Serialize, Deserialize)]
pub struct Settings {
    version: u32,
    auto_paste: bool,
    #[serde(default)]
    on_conflict: String,
    hotkeys: HashMap<String, Option<String>>,
}

#[tauri::command]
async fn read_settings() -> Result<serde_json::Value, String> {
    cli::run_cli(vec!["show".into(), "--json".into()]).await
}

#[tauri::command]
async fn write_settings(settings: Settings) -> Result<(), String> {
    // Route through the CLI so the validation logic (hotkey parse, within-set
    // conflicts) runs in Python — the single source of truth for binding rules.
    let mut args = vec!["reset".into()];
    for (k, v) in settings.hotkeys.iter() {
        match v {
            Some(c) => args.extend(["bind".into(), k.clone(), c.clone()]),
            None => args.extend(["bind".into(), k.clone(), "--clear".into()]),
        }
    }
    // auto-paste: the CLI exposes it as a top-level settings key; write it via
    // a small helper on the Python side.
    let _ = args;
    // (The simplest correct path is to let the frontend's `save_settings`
    // invoke `passist show` + `passist bind` + `passist apply-safe-fallbacks`;
    // but the GUI does the file write directly to avoid an extra round-trip.)
    let s = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    let p = data_dir().join("settings.json");
    std::fs::create_dir_all(p.parent().unwrap()).ok();
    std::fs::write(p, s).map_err(|e| e.to_string())
}

#[tauri::command]
async fn list_bindings() -> Result<serde_json::Value, String> {
    cli::run_cli(vec!["list-bindings".into(), "--json".into()]).await
}

#[tauri::command]
async fn bind(stage: String, combo: Option<String>) -> Result<(), String> {
    let mut args = vec!["bind".into(), stage];
    match combo {
        Some(c) => args.push(c),
        None => args.push("--clear".into()),
    }
    cli::run_cli(args).await.map(|_| ()).map_err(|e| format!("{e}"))
}

#[tauri::command]
async fn apply_safe_fallbacks() -> Result<(), String> {
    cli::run_cli(vec!["apply-safe-fallbacks".into()]).await.map(|_| ()).map_err(|e| format!("{e}"))
}

#[tauri::command]
async fn reset_settings() -> Result<(), String> {
    cli::run_cli(vec!["reset".into()]).await.map(|_| ()).map_err(|e| format!("{e}"))
}

#[tauri::command]
async fn set_auto_paste(app: tauri::AppHandle, on: bool) -> Result<(), String> {
    // Read-modify-write so the hotkey bindings are preserved.
    let path = data_dir().join("settings.json");
    let mut obj: serde_json::Value = match std::fs::read_to_string(&path) {
        Ok(s) => serde_json::from_str(&s).unwrap_or_default(),
        Err(_) => serde_json::json!({ "version": 1, "auto_paste": false, "hotkeys": {} }),
    };
    obj["auto_paste"] = serde_json::Value::Bool(on);
    let out = serde_json::to_string_pretty(&obj).unwrap_or_default();
    std::fs::create_dir_all(path.parent().unwrap()).ok();
    std::fs::write(&path, out).map_err(|e| e.to_string())?;
    let _ = app;
    Ok(())
}

#[tauri::command]
async fn version() -> String {
    "0.1.0".to_string()
}

// ============================ Tray / window ================================

fn tray_menu(app: &tauri::AppHandle) -> Menu<()> {
    let mut items: Vec<MenuItem<String, String>> = Vec::new();
    for (i, stage) in STAGES.iter().enumerate() {
        let label = format!("{}. {}  (fire)", i + 1, STAGE_NAMES[i]);
        let item = MenuItem::with_id(
            app,
            format!("tray-{stage}"),
            label,
            true,
            None::<&str>,
        );
        items.push(item);
    }
    items.push(MenuItem::with_id(app, "tray-next", "▶  Next stage", true, None::<&str>));
    items.push(MenuItem::with_id(app, "tray-open", "Open window", true, None::<&str>));
    let menu = Menu::with_items(app, &items).expect("tray menu");
    menu
}

#[tauri::command]
async fn quit(app: tauri::AppHandle) {
    app.exit(0);
}

// ============================== app entry ===================================

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .manage(App {
            last_render: Mutex::new(None),
            active_feature: Mutex::new(None),
        })
        .plugin(tauri_plugin_global_shortcut::init())
        .plugin(tauri_plugin_clipboard_manager::init())
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_autostart::init(tauri_plugin_autostart::MacosLauncher::LaunchAgent, None))
        .setup(|app| {
            let handle = app.handle().clone();

            // Build the tray with all six stages + next + open.
            let menu = tray_menu(&handle);
            let _tray = TrayIconBuilder::with_id("main")
                .tooltip("PromptAssist")
                .icon(app.default_window_icon().cloned().unwrap_or_else(|| {
                    // Fallback: blank icon (replaced by bundled asset on a real build).
                    tauri::Image::new_owned([0u8; 0], 0, 0)
                }))
                .menu(&menu)
                .on_menu_event(|tray, event| {
                    let app = tray.app_handle();
                    match event.id.as_ref() {
                        s if s.starts_with("tray-") && !s.starts_with("tray-open") && !s.starts_with("tray-next") => {
                            let stage = s.strip_prefix("tray-").unwrap_or("");
                            fire_stage(app, stage);
                        }
                        "tray-next" => fire_stage(app, "__next__"),
                        "tray-open" => {
                            if let Some(w) = app.get_webview_window("main") {
                                let _ = w.show();
                                let _ = w.set_focus();
                            }
                        }
                        _ => {}
                    }
                })
                .build(app)
                .expect("build tray");

            // Wire up the global shortcuts from settings.json.
            shortcuts::install(&handle).ok();

            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            version,
            list_stage_ids,
            list_features,
            set_active_feature,
            new_feature,
            render_stage,
            render_all,
            sync_agent,
            read_settings,
            write_settings,
            list_bindings,
            bind,
            apply_safe_fallbacks,
            reset_settings,
            set_auto_paste,
            quit
        ])
        .run(tauri::generate_context!())
        .expect("error while running PromptAssist");
}

/// Fire a stage from the tray. If "__next__", advance from the last-fired stage.
fn fire_stage(app: &tauri::AppHandle, stage: &str) {
    let _ = app;
    // Rendering happens on the Python CLI side (async, tokio::spawn).
    let stage_owned = stage.to_string();
    tauri::async_runtime::spawn(async move {
        if stage_owned == "__next__" {
            let raw = tokio::fs::read(data_dir().join("features.json")).await.unwrap_or_default();
            let v: serde_json::Value = serde_json::from_slice(&raw).unwrap_or_default();
            let next = match v
                .get("features")
                .and_then(|a| a.as_array())
                .and_then(|a| a.first())
                .and_then(|f| f.get("last_fired_stage"))
                .and_then(|s| s.as_str())
            {
                Some(last) => next_stage_id(last),
                None => "research".to_string(),
            };
            let args = vec!["run".into(), next, "-".into()];
            let _ = cli::run_cli(args).await;
            return;
        }
        let args = vec!["run".into(), stage_owned.to_string(), "-".into()];
        let _ = cli::run_cli(args).await;
    });
}

fn next_stage_id(current: &str) -> String {
    const ORDER: [&str; 6] = ["research", "plan", "check-plan", "build", "continue", "review-code"];
    let idx = ORDER.iter().position(|s| *s == current).unwrap_or(0);
    if idx + 1 < ORDER.len() {
        ORDER[idx + 1].to_string()
    } else {
        "research".to_string()
    }
}