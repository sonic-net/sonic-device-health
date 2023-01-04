#! /bin/bash

if [ $# -eq 0 ]
then
    outf="LoM.tar.gz"
else
    outf="$1.tar.gz"
fi
rm -f ${outf}
find ./ -type f \( -iname \*.json -o -iname \*.py \) -print0 | tar -cvzf ${outf} --null --files-from -
echo "Created ${outf}"
