{
  description = "PiShock python tool flake";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs?ref=nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let pkgs = nixpkgs.legacyPackages.${system};
      in {
        packages.default = with pkgs.python3Packages;
          buildPythonPackage rec {
            propagatedBuildInputs = [
              requests
              platformdirs
              rich
              typer
              typing-extensions
              pyserial
              pkgs.esptool
            ];

            pname = "pishock";
            version = "1.0.3";
            format = "wheel";

            src = fetchPypi rec {
              inherit pname version format;
              sha256 =
                "952ba845d04a5fa4409409fed401d693be910dc5bb9049e2508aa87cb8049f77";
              dist = python;
              python = "py3";
              abi = "none";
              platform = "any";
            };
          };
      });
}
