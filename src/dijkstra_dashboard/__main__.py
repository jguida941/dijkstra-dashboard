import sys
from PyQt6.QtWidgets import QApplication
from dijkstra_dashboard.ui.main_window import MainWindow

def main():
    app = QApplication(sys.argv)

    # Set application style
    app.setStyle('Fusion')

    # Create and show the main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
