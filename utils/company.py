try:
    from PySide6.QtCore import QSettings
    _qs = QSettings("MayurSoft", "BillingSoftware")

    def COMPANY_NAME():
        return _qs.value("company_name", "Your Company Name")

    def COMPANY_ADDRESS():
        return _qs.value("company_address", "123 Business Street, City")

    def COMPANY_PHONE():
        return _qs.value("company_phone", "+91-000-000-0000")

except Exception:
    def COMPANY_NAME():
        return "Your Company Name"

    def COMPANY_ADDRESS():
        return "123 Business Street, City"

    def COMPANY_PHONE():
        return "+91-000-000-0000"
