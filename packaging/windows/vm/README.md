# Building the Windows app from Linux

This runs a real Windows 11 in a container (`dockurr/windows`, QEMU with KVM) and builds inside it. It needs
`/dev/kvm`, about 8 GB of RAM, 4 cores and 64 GB of disk, and it downloads Windows from Microsoft, whose licence
terms apply. Installing takes about 25 minutes.

One command does all of this: `packaging/windows/vm/build-from-linux.sh` (not yet run end to end as a single script; the steps below are the ones that produced the v0.1.1 build).

```
mkdir -p /tmp/winbuild/{storage,shared,oem}
git archive HEAD | tar -x -C /tmp/winbuild/shared/src-tree   # create src-tree first
cp packaging/windows/vm/install.bat /tmp/winbuild/oem/install.bat
cp packaging/windows/vm/build.bat /tmp/winbuild/shared/run.bat.initial
docker run -d --name pvysics-win -e VERSION=11 -e RAM_SIZE=8G -e CPU_CORES=4 -e DISK_SIZE=64G \
  -p 127.0.0.1:8006:8006 --device /dev/kvm --device /dev/net/tun --cap-add NET_ADMIN \
  -v /tmp/winbuild/storage:/storage -v /tmp/winbuild/shared:/shared -v /tmp/winbuild/oem:/oem dockurr/windows
```

When `/tmp/winbuild/shared/DONE` appears, the zip and setup exe are in `/tmp/winbuild/shared/out`. Watch the
screen at http://127.0.0.1:8006. Copying the source needs `xcopy /H` (it holds the hidden `.python-version`), and
Inno Setup comes from its GitHub release, https://github.com/jrsoftware/issrc/releases. To build again without
reinstalling Windows, replace `src-tree` and drop a `run.bat` into the shared folder: a task checks for it each minute.
