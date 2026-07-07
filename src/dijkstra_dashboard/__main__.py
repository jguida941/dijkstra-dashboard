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
    manager = get_theme_manager()
    # Custom themes must register BEFORE load_from_config so a persisted custom
    # theme id resolves instead of falling back to the default.
    manager.load_custom_themes()
    manager.load_from_config()
    app.setWindowIcon(make_app_icon(current_theme()))

    # Create and show the main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == '__main__':
    main()
