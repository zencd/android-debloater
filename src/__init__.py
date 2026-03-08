class AbortException(Exception):
    # use this exception to abort a business logics, when you don't want much panic in logs
    # example: an adb command fails because no device connected
    pass