{
  description = "mascot flake";

  inputs = {
    self.submodules = true;
    nixpkgs.url = "nixpkgs/nixos-unstable";
    flake-parts.url = "github:hercules-ci/flake-parts";
  };

  outputs = inputs@{ flake-parts, ... }:
    flake-parts.lib.mkFlake { inherit inputs; } {
      systems = [ "x86_64-linux" "aarch64-linux" ];

      perSystem = { config, pkgs, ... }: {
        packages = {
          mascot = pkgs.callPackage ./nix/package.nix { inherit (config.packages) mascot-unwrapped; };
          mascot-unwrapped = pkgs.callPackage ./nix/unwrapped.nix { };
          default = config.packages.mascot;
        };
      };
    };
}
