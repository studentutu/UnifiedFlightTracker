#pragma once

#include <QMainWindow>
#include <QSortFilterProxyModel>
#include <QUrl>

#include "TrackerClient.h"

class QLineEdit;
class QTableView;
class KpiBar;
class PolarSkyView;
class AltitudeStripChart;
class FlightModel;

class MainWindow : public QMainWindow {
    Q_OBJECT
public:
    MainWindow(QUrl baseUrl, TrackerClient::Observer obs, int intervalMs,
               QWidget *parent = nullptr);
    ~MainWindow() override;

private slots:
    void onFlights(const QList<Flight> &flights, const QStringList &messages, double elapsedMs);
    void onError(const QString &msg);
    void onSkyPick(const QString &hex);
    void onTableSelectionChanged();

private:
    void applyDarkPalette();
    void buildMenu();
    QString labelFor(const QString &hex) const;

    KpiBar               *m_kpi;
    PolarSkyView         *m_sky;
    QTableView           *m_view;
    QLineEdit            *m_filter;
    AltitudeStripChart   *m_strip;
    FlightModel          *m_model;
    QSortFilterProxyModel*m_proxy;
    TrackerClient        *m_client;
};
