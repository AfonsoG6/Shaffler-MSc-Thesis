rm -rf shadow.data shadow.log
cp -r ~/rendezmix/loop/* shadow.data.template/hosts/torclient

# Run the Tor minimal test and store output in shadow.log
shadow --template-directory shadow.data.template tor-minimal.yaml > shadow.log

./verify.sh
