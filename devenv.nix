{ pkgs, ... }:

{
  # Enable Python support
  languages.python.enable = true;

  # Use a virtual environment and install packages from requirements.txt
  languages.python.venv.enable = true;
  languages.python.venv.requirements = ''
    parsita
    click
  '';

  # Add other development tools
  packages = [
    pkgs.git
  ];

  # Commands to run when entering the shell
  enterShell = ''
    echo "Entered ledger-parsita devenv environment."
    echo "Python version: $(python --version)"
  '';
}
