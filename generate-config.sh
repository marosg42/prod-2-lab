#!/bin/bash
# $1 fcelab dir
# $2 production dir
# $3 outdir

set -e
cp -r $2 $3
mkdir -p $3/generated/maas

COPY_FROM_LAB="bucketsconfig.yaml hosts.yaml nodes.yaml"

for i in $COPY_FROM_LAB ; do
    cp $1/config/$i $3/config/
done

# change mtu 9000 to 1500
sed -i "s/9000/1500/" $3/config/networks.yaml

./modify_master.py $2/config/master.yaml $3/config/master.yaml

if [ $# -eq 4 ]  && [ $4 == 'k8s' ]
then
    ./modify_bundle.py $2/config/kubernetes_bundle.yaml $3/config/kubernetes_bundle.yaml k8s
else
    ./modify_bundle.py $2/config/bundle.yaml $3/config/bundle.yaml
fi

set +e
