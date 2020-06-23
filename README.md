# prod-2-lab

Convert production config to fce-lab config.

It will remove LMA apps and relations, reduce haclusters to 1 and do some other minor tweaks.

`./generate-config.sh fce-lab/ prod/ out/`

- `fce-lab/` is any fce-lab branch (a.k.a. `project` directory created by `fce_cloud`).

- `prod/` is a directory with any fcb branch suitable for production silo.

- `out/` where the results go. Run `fce` then from this dir.

**Note:** probably not going to work with fkb branches, would need some modifications.
