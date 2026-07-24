#pragma once

#include <QObject>
#include <QString>
#include <QUrl>
#include <QTimer>

#include "Flight.h"

class QNetworkAccessManager;
class QNetworkReply;

class TrackerClient : public QObject {
    Q_OBJECT
public:
    struct Observer { double lat; double lon; double radiusNm; };

    TrackerClient(QUrl baseUrl, Observer obs, int intervalMs, QObject *parent = nullptr);

    void start();
    void stop();

signals:
    void flightsReceived(const QList<Flight> &flights, const QStringList &messages, double elapsedMs);
    void error(const QString &message);

private slots:
    void poll();
    void onReplyFinished();

private:
    QUrl                     m_baseUrl;
    Observer                 m_observer;
    QTimer                   m_timer;
    QNetworkAccessManager   *m_nam;
    QNetworkReply           *m_reply = nullptr;
    qint64                   m_requestStartedNs = 0;
};
