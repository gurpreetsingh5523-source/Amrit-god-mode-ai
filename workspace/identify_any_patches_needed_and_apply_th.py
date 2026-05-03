import os
import subprocess

def apply_patch(patch_file):
    try:
        subprocess.run(['patch', '-p1', '<', patch_file], check=True)
        print(f"Patch {patch_file} applied successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Failed to apply patch {patch_file}: {e}")
        return False

def find_and_apply_patches(patch_directory):
    patches = [f for f in os.listdir(patch_directory) if f.endswith('.patch')]
    all_applied = True
    for patch in patches:
        full_path = os.path.join(patch_directory, patch)
        if not apply_patch(full_path):
            all_applied = False
    return all_applied

if __name__ == "__main__":
    patch_directory = './patches'
    print("Scanning directory:", patch_directory)
    success = find_and_apply_patches(patch_directory)
    if success:
        print("All patches applied successfully.")
    else:
        print("Some patches failed to apply. Check logs for details.")