#include <QApplication>
#include <QCommandLineOption>
#include <QCommandLineParser>
#include <QUrl>

#include "MainWindow.h"

int main(int argc, char *argv[]) {
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName("vcqtdb");
    QCoreApplication::setApplicationVersion("1.0");

    QCommandLineParser parser;
    parser.setApplicationDescription("Unified Flight Tracker dashboard (Qt/C++)");
    parser.addHelpOption();
    parser.addVersionOption();

    QCommandLineOption url("url", "backend base URL", "url",
                           qEnvironmentVariable("TRACKER_URL", "http://localhost:5001"));
    QCommandLineOption lat("lat", "observer latitude (deg)", "lat",
                           qEnvironmentVariable("TRACKER_LAT", "39.5478"));
    QCommandLineOption lon("lon", "observer longitude (deg)", "lon",
                           qEnvironmentVariable("TRACKER_LON", "-76.1347"));
    QCommandLineOption rad("radius", "search radius (NM)", "nm",
                           qEnvironmentVariable("TRACKER_RADIUS", "150"));
    QCommandLineOption iv("interval", "poll interval (s)", "s",
                          qEnvironmentVariable("TRACKER_INTERVAL", "5"));
    parser.addOptions({url, lat, lon, rad, iv});
    parser.process(app);

    TrackerClient::Observer obs{
        parser.value(lat).toDouble(),
        parser.value(lon).toDouble(),
        parser.value(rad).toDouble(),
    };
    const int intervalMs = int(parser.value(iv).toDouble() * 1000.0);

    MainWindow w(QUrl(parser.value(url)), obs, intervalMs);
    w.show();
    return app.exec();
}
