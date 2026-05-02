import ast
import shutil
from pathlib import Path
from experience_log import ExperienceLog

def validate_patch(file_path: str, old_code: str, new_code: str):
    """Validate new_code for syntax safety using ast.parse."""
    try:
        ast.parse(new_code)
        return True, ""
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

def backup_file(file_path: str):
    bak_path = f"{file_path}.bak"
    shutil.copy2(file_path, bak_path)
    return bak_path

def restore_backup(file_path: str):
    bak_path = f"{file_path}.bak"
    if Path(bak_path).exists():
        shutil.copy2(bak_path, file_path)
        return True
    return False

def record_patch_failure(agent: str, file_path: str, reason: str, task: str = "patch"): 
    log = ExperienceLog()
    log.record(agent=agent, action="patch_failed", result={"file": file_path, "reason": reason}, task=task, success=False)
    log.save()

def auto_recover(file_path: str, logger=None):
    if restore_backup(file_path):
        if logger:
            logger.warning(f"[AUTO-RECOVER] Restored backup for {file_path}")
        return True
    if logger:
        logger.error(f"[AUTO-RECOVER] No backup found for {file_path}")
    return False
