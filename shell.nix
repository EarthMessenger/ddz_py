let
  pkgs = import <nixpkgs> {};
in pkgs.mkShell {
  packages = [
    (pkgs.python313.withPackages (python-pkgs: [
      python-pkgs.colorama
      python-pkgs.prompt-toolkit
      python-pkgs.wcwidth
    ]))
  ];
}
