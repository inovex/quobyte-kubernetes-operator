#!/bin/bash

IFS=',' read -r -a array <<< "$DISKS"
counter=0
for disk in "${array[@]}"
do
    if file -sL /dev/${disk} | grep "data" &> /dev/null; then
        parted /dev/${disk} mklabel gpt
        parted /dev/${disk} mkpart primary 2048s 100%
    fi

    if file -sL /dev/${disk} | grep "data" &> /dev/null; then
        exit 1
    fi

    if [ ! -f /dev/${disk}1 ]; then
        exit 1
    fi

    if ! file -sL /dev/${disk}1 | grep "XFS filesystem" &> /dev/null; then
        mkfs.xfs -isize=1024 /dev/${disk}1
    fi

    if ! file -sL /dev/${disk}1 | grep "XFS filesystem" &> /dev/null; then
        exit 1
    fi

    mkdir -p /devices/disk${counter}

    if ! grep /dev/${disk}1 /etc/fstab &> /dev/null; then
        echo "/dev/${disk}1 /mnt/data/disk${counter} xfs relatime,nodiscard 0 2" >> /etc/fstab
    fi

    if ! grep /dev/${disk}1 /proc/mounts &> /dev/null; then
        mount /dev/${disk}1 /devices/disk${counter}
    fi

    if [ ! -f /devices/disk${counter}/QUOBYTE_DEV_SETUP ]; then
      cat > /devices/disk${counter}/QUOBYTE_DEV_SETUP <<EOF
device.serial=$(uuidgen)
device.model=Volume
device.type=DATA_DEVICE
EOF
    fi
    let counter++
done

# TODO nice to have
#echo deadline > /sys/block/sdX/queue/scheduler
#echo 4096 > /sys/block/sdX/queue/nr_requests

#echo 5 > /proc/sys/vm/dirty_background_ratio
#echo 10 > /proc/sys/vm/dirty_ratio