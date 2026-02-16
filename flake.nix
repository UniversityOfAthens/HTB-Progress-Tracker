{
  description = "HTB Progress Tracker environment";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-unstable";
  };

  outputs = { self, nixpkgs }: let
    system = "x86_64-linux";
    pkgs = import nixpkgs {
      inherit system;
    };
    pythonEnv = pkgs.python3.withPackages (ps: with ps; [
      requests
      discordpy
      python-dotenv
      tzdata
      black
    ]);
  in {
    devShells.${system}.default = pkgs.mkShell {
      packages = [
        pythonEnv
      ];
    };
  };
}
