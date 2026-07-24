#include "TrackerClient.h"

#include <QElapsedTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUrlQuery>
#include <QDateTime>

TrackerClient::TrackerClient(QUrl baseUrl, Observer obs, int intervalMs, QObject *parent)
    : QObject(parent)
    , m_baseUrl(std::move(baseUrl))
    , m_observer(obs)
    , m_nam(new QNetworkAccessManager(this))
{
    m_timer.setInterval(intervalMs);
    m_timer.setSingleShot(false);
    connect(&m_timer, &QTimer::timeout, this, &TrackerClient::poll);
}

void TrackerClient::start() {
    poll();
    m_timer.start();
}

void TrackerClient::stop() {
    m_timer.stop();
    if (m_reply) {
        m_reply->abort();
        m_reply->deleteLater();
        m_reply = nullptr;
    }
}

void TrackerClient::poll() {
    if (m_reply) {
        // Previous request still in flight — skip this tick.
        return;
    }
    QUrl url = m_baseUrl;
    QString path = url.path();
    if (!path.endsWith('/')) path += '/';
    url.setPath(path + "api/flights");

    QUrlQuery q;
    q.addQueryItem("lat",    QString::number(m_observer.lat,      'f', 6));
    q.addQueryItem("lon",    QString::number(m_observer.lon,      'f', 6));
    q.addQueryItem("radius", QString::number(m_observer.radiusNm, 'f', 2));
    url.setQuery(q);

    QNetworkRequest req(url);
    req.setHeader(QNetworkRequest::UserAgentHeader, "vcqtdb/1.0");
    req.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                     QNetworkRequest::NoLessSafeRedirectPolicy);
    req.setTransferTimeout(8000);

    m_requestStartedNs = QDateTime::currentMSecsSinceEpoch();
    m_reply = m_nam->get(req);
    connect(m_reply, &QNetworkReply::finished, this, &TrackerClient::onReplyFinished);
}

void TrackerClient::onReplyFinished() {
    QNetworkReply *reply = m_reply;
    m_reply = nullptr;
    if (!reply) return;
    reply->deleteLater();

    const double elapsedMs = double(QDateTime::currentMSecsSinceEpoch() - m_requestStartedNs);

    if (reply->error() != QNetworkReply::NoError) {
        emit error(reply->errorString());
        return;
    }
    const QByteArray body = reply->readAll();
    QJsonParseError perr{};
    const QJsonDocument doc = QJsonDocument::fromJson(body, &perr);
    if (perr.error != QJsonParseError::NoError || !doc.isObject()) {
        emit error(QStringLiteral("bad JSON: %1").arg(perr.errorString()));
        return;
    }
    const QJsonObject obj = doc.object();

    QList<Flight> out;
    const QJsonArray arr = obj.value("flights").toArray();
    out.reserve(arr.size());
    for (const auto &v : arr) {
        const QJsonObject f = v.toObject();
        Flight fl;
        fl.hexId        = f.value("hex_id").toString();
        fl.callsign     = f.value("callsign").toString();
        fl.type         = f.value("type").toString();
        fl.source       = f.value("source").toString();
        fl.lat          = f.value("lat").toDouble();
        fl.lon          = f.value("lon").toDouble();
        fl.altitudeFt   = f.value("altitude").toDouble();
        fl.speedKt      = f.value("speed").toDouble();
        fl.headingDeg   = f.value("heading").toDouble();
        fl.distanceNm   = f.value("distance_from_obs").toDouble();
        fl.azimuthDeg   = f.value("azimuth").toDouble();
        fl.elevationDeg = f.value("elevation").toDouble();
        out.push_back(fl);
    }

    QStringList messages;
    const QJsonArray marr = obj.value("messages").toArray();
    for (const auto &m : marr) messages << m.toString();

    emit flightsReceived(out, messages, elapsedMs);
}
