from pathlib import Path

from adb_shell.auth.keygen import keygen

if __name__ == '__main__':
    key = str(Path.home() / '.android-debloater/adbkey')
    keygen(key)

    from adb_shell.adb_device import AdbDeviceTcp, AdbDeviceUsb
    from adb_shell.auth.sign_pythonrsa import PythonRSASigner

    # Load the public and private keys
    with open(key) as f:
        priv = f.read()
    with open(key + '.pub') as f:
        pub = f.read()
    signer = PythonRSASigner(pub, priv)

    # Connect
    device2 = AdbDeviceUsb()
    device2.connect(rsa_keys=[signer], auth_timeout_s=0.9)
