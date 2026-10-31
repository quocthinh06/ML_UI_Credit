"""Optional legacy Windows desktop launcher."""
import sys
from PyQt6.QtWidgets import QApplication
from creditrisk.ui import MainWindow

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setApplicationName("CreditRisk AI")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
