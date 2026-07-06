import sys
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import QApplication
from dijkstra_dashboard.ui.main_window import MainWindow
from dijkstra_dashboard.ui.theme import current_theme, get_theme_manager, make_app_icon

def main():
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("dijkstra-dashboard")
    app.setApplicationDisplayName("Dijkstra Visualizer")
    app.setOrganizationName("dijkstra-dashboard")

    # Set application style
    app.setStyle('Fusion')
    get_theme_manager().load_from_config()
    app.setWindowIcon(make_app_icon(current_theme()))

    # Create and show the main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
