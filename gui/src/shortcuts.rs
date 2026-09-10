/// Install global shortcuts from `settings.json` using Tauri's
/// `tauri-plugin-global-shortcut` (wraps Win32 `RegisterHotKey` on Windows).
/// `parse_combo` mirrors the Python `passist.hotkeys.parse` so both sides
/// agree on what's a valid binding.
use std::collections::HashMap;

use tauri::AppHandle;
use tauri_plugin_global_shortcut::{Code, GlobalShortcutExt, Modifiers, Shortcut};

use crate::data_dir;

pub fn install(app: &AppHandle) -> Result<(), String> {
    let hk = read_hotkeys_from_settings()?;
    for (stage, combo) in hk.iter() {
        let combo = match combo {
            Some(c) if !c.is_empty() => c.clone(),
            _ => continue,
        };
        let s = match parse_combo(&combo) {
            Some(s) => s,
            None => {
                eprintln!("[passist-gui] skipping invalid hotkey {stage} = {combo}");
                continue;
            }
        };
        match app.global_shortcut().register(s) {
            Ok(h) => {
                let app2 = app.clone();
                let stage_owned = stage.clone();
                h.on_shortcut(move |_app, _shortcut, event| {
                    if event.state.is_pressed() {
                        let app3 = app2.clone();
                        let st = stage_owned.clone();
                        tauri::async_runtime::spawn(async move {
                            let _ = app3;
                            let _ = st;
                            crate::fire_stage(&app3, &st);
                        });
                    }
                });
            }
            Err(e) => eprintln!("[passist-gui] failed to register {stage} = {combo}: {e}"),
        }
    }
    Ok(())
}

fn read_hotkeys_from_settings() -> Result<HashMap<String, Option<String>>, String> {
    let path = data_dir().join("settings.json");
    let raw = std::fs::read_to_string(&path).unwrap_or_else(|_| r#"{"hotkeys":{}}"#.into());
    let v: serde_json::Value = serde_json::from_str(&raw).map_err(|e| e.to_string())?;
    let mut out = HashMap::new();
    if let Some(obj) = v.get("hotkeys").and_then(|h| h.as_object()) {
        for (k, val) in obj {
            match val {
                serde_json::Value::String(s) => {
                    out.insert(k.clone(), Some(s.clone()));
                }
                serde_json::Value::Null => out.insert(k.clone(), None),
                _ => {}
            }
        }
    }
    Ok(out)
}

/// Parse `"Ctrl+Shift+P"` / `"F5"` into a `Shortcut`. Returns `None` for
/// invalid input (the Python CLI remains source of truth for validation).
pub fn parse_combo(combo: &str) -> Option<Shortcut> {
    let parts: Vec<&str> = combo
        .split('+')
        .map(|s| s.trim())
        .filter(|s| !s.is_empty())
        .collect();
    if parts.is_empty() {
        return None;
    }
    let mut mods = Modifiers::empty();
    let mut key: Option<Code> = None;
    for p in parts {
        let lower = p.to_ascii_lowercase();
        if lower == "ctrl" || lower == "control" {
            mods |= Modifiers::CONTROL;
        } else if lower == "cmd" || lower == "meta" {
            mods |= Modifiers::COMMAND;
        } else if lower == "alt" || lower == "option" {
            mods |= Modifiers::ALT;
        } else if lower == "shift" {
            mods |= Modifiers::SHIFT;
        } else if let Some(c) = parse_key(p) {
            key = Some(c);
        } else {
            return None;
        }
    }
    let key = key?;
    Some(Shortcut::new(mods, key))
}

fn parse_key(s: &str) -> Option<Code> {
    let lower = s.to_ascii_lowercase();
    if let Ok(n) = s.parse::<u8>() {
        return Some(Code::Digit(n % 10));
    }
    if let Some(rest) = lower.strip_prefix("f") {
        let n = rest.parse::<u8>().ok()?;
        return Some(match n {
            1 => Code::F1, 2 => Code::F2, 3 => Code::F3, 4 => Code::F4,
            5 => Code::F5, 6 => Code::F6, 7 => Code::F7, 8 => Code::F8,
            9 => Code::F9, 10 => Code::F10, 11 => Code::F11, 12 => Code::F12,
            _ => return None,
        });
    }
    if lower.len() == 1 {
        return Some(match lower.as_bytes()[0] {
            b'a' => Code::A, b'b' => Code::B, b'c' => Code::C, b'd' => Code::D,
            b'e' => Code::E, b'f' => Code::F, b'g' => Code::G, b'h' => Code::H,
            b'i' => Code::I, b'j' => Code::J, b'k' => Code::K, b'l' => Code::L,
            b'm' => Code::M, b'n' => Code::N, b'o' => Code::O, b'p' => Code::P,
            b'q' => Code::Q, b'r' => Code::R, b's' => Code::S, b't' => Code::T,
            b'u' => Code::U, b'v' => Code::V, b'w' => Code::W, b'x' => Code::X,
            b'y' => Code::Y, b'z' => Code::Z,
            _ => return None,
        });
    }
    match lower.as_str() {
        "space" => Some(Code::Space),
        "enter" | "return" => Some(Code::Enter),
        "tab" => Some(Code::Tab),
        "escape" | "esc" => Some(Code::Escape),
        "backspace" => Some(Code::Backspace),
        "delete" => Some(Code::Delete),
        "home" => Some(Code::Home),
        "end" => Some(Code::End),
        "pageup" => Some(Code::PageUp),
        "pagedown" => Some(Code::PageDown),
        _ => None,
    }
}