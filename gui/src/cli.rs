/// Thin wrapper around the `passist` Python CLI. The GUI never renders
/// prompts itself — every render/transform goes through the Python core, so
/// there is exactly one implementation of the workflow.
///
/// Every call passes `--data-dir <user-state>` so the CLI reads the same
/// `features.json` / `settings.json` that the Python CLI uses.
use tokio::process::Command;

use crate::{data_dir, passist_bin};

pub async fn run_cli(args: Vec<String>) -> Result<String, String> {
    let mut full = vec![passist_bin()];
    full.push("--data-dir".into());
    full.push(data_dir().to_string_lossy().into());
    full.extend(args.into_iter());

    let out = Command::new(full[0].as_str())
        .args(&full[1..])
        .output()
        .await
        .map_err(|e| format!("failed to spawn passist: {e}"))?;

    if !out.status.success() {
        let stderr = String::from_utf8_lossy(&out.stderr).into_owned();
        return Err(format!(
            "passist exited {:?}: {}",
            out.status.code(),
            stderr.trim()
        ));
    }
    Ok(String::from_utf8_lossy(&out.stdout).into_owned())
}