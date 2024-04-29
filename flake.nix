{
  description = "View/select the URLs in an email message or file";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs";
  };

  outputs = {
    self,
    nixpkgs,
  }: let
    systems = ["x86_64-linux" "i686-linux" "aarch64-linux"];
    forAllSystems = f:
      nixpkgs.lib.genAttrs systems (system:
        f rec {
          pkgs = nixpkgs.legacyPackages.${system};
          commonPackages = builtins.attrValues {
            inherit
              (pkgs.python312Packages)
              python
              urwid
              ;
          };
        });
  in {
    devShells = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
      default = pkgs.mkShell {
        packages = commonPackages ++ [pkgs.pandoc];
        shellHook = ''
          alias urlscan="python -m urlscan"
          export PYTHONPATH="$PYTHONPATH:$PWD"
        '';
      };
    });
    packages = forAllSystems ({
      pkgs,
      commonPackages,
    }: {
      default = pkgs.python312Packages.buildPythonApplication {
        name = "urlscan";
        pname = "urlscan";
        format = "pyproject";
        src = ./.;
        nativeBuildInputs = builtins.attrValues {
          inherit
            (pkgs)
            git
            ;
          inherit
            (pkgs.python312Packages)
            hatchling
            hatch-vcs
            ;
        };
        propagatedBuildInputs = commonPackages;
        meta = {
          description = "View/select the URLs in an email message or file";
          homepage = "https://github.com/firecat53/urlscan";
          license = pkgs.lib.licenses.gpl2Plus;
          maintainers = ["firecat53"];
          platforms = systems;
        };
      };
    });
  };
}
