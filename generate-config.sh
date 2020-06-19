#!/bin/bash
# $1 fcelab dir
# $2 production dir
# $3 outdir

rm -rf $3
cp -r $2 $3
mkdir -p $3/generated/maas

COPY_FROM_LAB="bucketsconfig.yaml hosts.yaml nodes.yaml"

for i in $COPY_FROM_LAB ; do
    cp $1/config/$i $3/config/
done

cp $1/generated/maas/virsh_rsa* $3/generated/maas

# change mtu 9000 to 1500
sed -i "s/9000/1500/" $3/config/networks.yaml

./modify_master.py $2/config/master.yaml $3/config/master.yaml
./modify_bundle.py $2/config/bundle.yaml $3/config/bundle.yaml


