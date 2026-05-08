import os
import subprocess
import sys


def run_command(command, description):
    print(f"\n--- {description} ---")
    try:
        # Use shell=True for Windows compatibility with certain CLI tools
        result = subprocess.run(command, shell=True, check=False, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(f"Error/Warnings:\n{result.stderr}")
        return result.returncode == 0
    except Exception as e:
        print(f"Failed to execute {command}: {e}")
        return False


def main():
    print("Starting FleetTracker Master Verification...")

    # 1. Formatting
    fmt_ok = run_command("ruff format .", "Beautifying Code (Ruff Format)")

    # 2. Linting
    lint_ok = run_command("ruff check . --fix", "Bug Hunting (Ruff Check)")

    # 3. Type Checking
    type_ok = run_command("mypy . --ignore-missing-imports", "Type Safety Audit (Mypy)")

    # 4. Security Check (Dependencies)
    sec_dep_ok = run_command("pip-audit", "Dependency Security Audit (pip-audit)")

    # 5. Security Check (Code)
    sec_code_ok = run_command("bandit -r src/ -ll", "Code Security Audit (Bandit)")

    # 6. Complexity Check
    complex_ok = run_command("radon cc src/ -s -nb", "Code Complexity Audit (Radon)")

    print("\n" + "=" * 40)
    if all([fmt_ok, lint_ok, type_ok, sec_dep_ok, sec_code_ok, complex_ok]):
        print("PASSED: All systems are green. Ready for Deployment!")
        sys.exit(0)
    else:
        print("WARNING: Some checks found issues. Review the logs above.")
        sys.exit(1)


if __name__ == "__main__":
    # Ensure we are in the root directory
    os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    main()
