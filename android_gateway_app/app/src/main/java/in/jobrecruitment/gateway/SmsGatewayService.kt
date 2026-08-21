package `in`.jobrecruitment.gateway

import android.app.*
import android.content.*
import android.os.*
import android.telephony.SmsManager
import android.telephony.SubscriptionInfo
import android.telephony.SubscriptionManager
import androidx.core.app.NotificationCompat
import com.google.gson.Gson
import com.google.gson.JsonObject
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit
import kotlin.concurrent.thread

class SmsGatewayService : Service() {

    private val CHANNEL_ID = "JR_SMS_GATEWAY_CHANNEL"
    private val NOTIFICATION_ID = 8492
    private var wakeLock: PowerManager.WakeLock? = null
    private var isRunning = false
    private val gson = Gson()
    private val jsonMediaType = "application/json; charset=utf-8".toMediaType()

    private val httpClient = OkHttpClient.Builder()
        .connectTimeout(15, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .writeTimeout(15, TimeUnit.SECONDS)
        .build()

    companion object {
        const val ACTION_START = "ACTION_START"
        const val ACTION_STOP = "ACTION_STOP"
        const val SMS_SENT_ACTION = "in.jobrecruitment.gateway.SMS_SENT"
        const val SMS_DELIVERED_ACTION = "in.jobrecruitment.gateway.SMS_DELIVERED"
    }

    override fun onCreate() {
        super.onCreate()
        createNotificationChannel()
        val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
        wakeLock = powerManager.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "JobRecruitment::SmsGatewayWakeLock")
        wakeLock?.acquire(12 * 60 * 60 * 1000L) // 12 hours max safety
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val action = intent?.action
        if (action == ACTION_STOP) {
            stopForegroundService()
            return START_NOT_STICKY
        }

        val serverUrl = intent?.getStringExtra("server_url") ?: "https://sms.jobrecruitment.in"
        val pairingCode = intent?.getStringExtra("pairing_code") ?: ""
        val preferredSimSlot = intent?.getIntExtra("sim_slot", 0) ?: 0

        startForeground(NOTIFICATION_ID, buildNotification("Listening for Cloud Campaigns...", pairingCode))

        if (!isRunning) {
            isRunning = true
            startGatewayLoop(serverUrl, pairingCode, preferredSimSlot)
        }

        return START_STICKY
    }

    private fun startGatewayLoop(serverUrl: String, pairingCode: String, simSlot: Int) {
        thread(start = true, isDaemon = true) {
            var lastHeartbeat = 0L

            while (isRunning) {
                try {
                    val now = System.currentTimeMillis()

                    // 1. Periodic Telemetry Heartbeat (every 10 seconds)
                    if (now - lastHeartbeat >= 10000L) {
                        sendHeartbeat(serverUrl, pairingCode, simSlot)
                        lastHeartbeat = now
                    }

                    // 2. Poll for Pending Dispatch Jobs
                    val pollUrl = "${serverUrl.trimEnd('/')}/api/gateway/poll?pairing_code=$pairingCode"
                    val request = Request.Builder()
                        .url(pollUrl)
                        .addHeader("User-Agent", "JR-Android-Gateway/1.0")
                        .build()

                    val response = httpClient.newCall(request).execute()
                    val body = response.body?.string() ?: "{}"
                    val json = gson.fromJson(body, JsonObject::class.java)

                    if (json.has("has_job") && json.get("has_job").asBoolean) {
                        val job = json.getAsJsonObject("job")
                        processCampaignJob(serverUrl, pairingCode, job, simSlot)
                    }

                } catch (e: Exception) {
                    // Backoff on transient network errors
                    Thread.sleep(3000)
                }

                Thread.sleep(2000)
            }
        }
    }

    private fun sendHeartbeat(serverUrl: String, pairingCode: String, simSlot: Int) {
        try {
            val batteryLevel = getBatteryLevel()
            val carrierName = getCarrierName(simSlot)
            val deviceModel = "${Build.MANUFACTURER} ${Build.MODEL}"

            val payload = JsonObject().apply {
                addProperty("pairing_code", pairingCode)
                addProperty("device_name", deviceModel)
                addProperty("carrier", carrierName)
                addProperty("battery", "$batteryLevel%")
                addProperty("is_online", true)
                addProperty("sim_slot", simSlot)
                addProperty("android_version", "Android ${Build.VERSION.RELEASE}")
            }

            val body = payload.toString().toRequestBody(jsonMediaType)
            val req = Request.Builder()
                .url("${serverUrl.trimEnd('/')}/api/gateway/heartbeat")
                .post(body)
                .build()

            httpClient.newCall(req).execute().close()
        } catch (ignored: Exception) {}
    }

    private fun processCampaignJob(serverUrl: String, pairingCode: String, job: JsonObject, simSlot: Int) {
        val candidates = job.getAsJsonArray("candidates") ?: return
        val template = job.get("template")?.asString ?: ""
        val role = job.get("role")?.asString ?: "Candidate"
        val location = job.get("location")?.asString ?: "India"
        val company = job.get("company")?.asString ?: "Job Recruitment"
        val baseDelay = job.get("delay")?.asFloat ?: 5.0f

        val total = candidates.size()
        updateNotification("Dispatching campaign: 0/$total sent", pairingCode)

        for (i in 0 until total) {
            if (!isRunning) break

            val cand = candidates.get(i).asJsonObject
            val name = if (cand.has("name") && !cand.get("name").isJsonNull) cand.get("name").asString else "Candidate"
            val phone = if (cand.has("phone")) cand.get("phone").asString else ""

            // Dynamic Spintax & Personalization Replacement
            var msg = template
                .replace("{name}", name)
                .replace("{role}", role)
                .replace("{location}", location)
                .replace("{company}", company)

            if (!msg.contains("JobRecruitment") && !msg.contains("HR")) {
                msg = "$msg - HR Team, JobRecruitment.in"
            }

            val isSuccess = dispatchSingleSms(phone, msg, simSlot)
            val logLine = "[${i + 1}/$total] ${if (isSuccess) "Sent to" else "Failed for"} $name (+91-$phone)"

            // Report Progress to Cloud Studio
            reportStatus(serverUrl, pairingCode, i + 1, isSuccess, logLine, (i + 1) == total)
            updateNotification("Dispatching: ${i + 1}/$total completed", pairingCode)

            if (i + 1 < total) {
                val jitter = baseDelay + (Math.random() * 2.5).toFloat()
                Thread.sleep((jitter * 1000).toLong())
            }
        }

        updateNotification("Active • Ready for next campaign", pairingCode)
    }

    private fun dispatchSingleSms(rawPhone: String, message: String, simSlot: Int): Boolean {
        val cleanPhone = rawPhone.filter { it.isDigit() }.takeLast(10)
        if (cleanPhone.length != 10) return false

        return try {
            val subManager = getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE) as? SubscriptionManager
            var subId = SubscriptionManager.getDefaultSubscriptionId()

            if (subManager != null) {
                try {
                    val activeSubs = subManager.activeSubscriptionInfoList
                    if (!activeSubs.isNullOrEmpty()) {
                        val selected = activeSubs.find { it.simSlotIndex == simSlot } ?: activeSubs[0]
                        subId = selected.subscriptionId
                    }
                } catch (ignored: SecurityException) {}
            }

            val smsManager = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
                getSystemService(SmsManager::class.java).createForSubscriptionId(subId)
            } else {
                @Suppress("DEPRECATION")
                SmsManager.getSmsManagerForSubscriptionId(subId)
            }

            val parts = smsManager.divideMessage(message)
            if (parts.size > 1) {
                smsManager.sendMultipartTextMessage(cleanPhone, null, parts, null, null)
            } else {
                smsManager.sendTextMessage(cleanPhone, null, message, null, null)
            }
            true
        } catch (e: Exception) {
            false
        }
    }

    private fun reportStatus(serverUrl: String, pairingCode: String, index: Int, isSent: Boolean, logLine: String, isFinished: Boolean) {
        try {
            val payload = JsonObject().apply {
                addProperty("pairing_code", pairingCode)
                addProperty("current_index", index)
                addProperty("is_sent", isSent)
                addProperty("log_line", logLine)
                addProperty("is_finished", isFinished)
            }
            val body = payload.toString().toRequestBody(jsonMediaType)
            val req = Request.Builder()
                .url("${serverUrl.trimEnd('/')}/api/gateway/report")
                .post(body)
                .build()
            httpClient.newCall(req).execute().close()
        } catch (ignored: Exception) {}
    }

    private fun getBatteryLevel(): Int {
        val bm = getSystemService(Context.BATTERY_SERVICE) as BatteryManager
        return bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)
    }

    private fun getCarrierName(simSlot: Int): String {
        try {
            val subManager = getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE) as? SubscriptionManager
            val activeSubs = subManager?.activeSubscriptionInfoList
            if (!activeSubs.isNullOrEmpty()) {
                val sub = activeSubs.find { it.simSlotIndex == simSlot } ?: activeSubs[0]
                return sub.carrierName?.toString() ?: "Cellular SIM"
            }
        } catch (ignored: Exception) {}
        return "Physical SIM"
    }

    private fun createNotificationChannel() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            val channel = NotificationChannel(
                CHANNEL_ID,
                "JobRecruitment SMS Gateway",
                NotificationManager.IMPORTANCE_LOW
            ).apply {
                description = "Keeps SMS Cellular Bridge active 24/7 for cloud recruitment campaigns"
            }
            val manager = getSystemService(NotificationManager::class.java)
            manager?.createNotificationChannel(channel)
        }
    }

    private fun buildNotification(statusText: String, pairingCode: String): Notification {
        val intent = Intent(this, MainActivity::class.java)
        val pendingIntent = PendingIntent.getActivity(
            this, 0, intent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )

        return NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("JobRecruitment Cellular Gateway")
            .setContentText("Status: $statusText (Code: $pairingCode)")
            .setSmallIcon(android.R.drawable.stat_notify_chat)
            .setContentIntent(pendingIntent)
            .setOngoing(true)
            .build()
    }

    private fun updateNotification(statusText: String, pairingCode: String) {
        val notification = buildNotification(statusText, pairingCode)
        val manager = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        manager.notify(NOTIFICATION_ID, notification)
    }

    private fun stopForegroundService() {
        isRunning = false
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        stopForeground(STOP_FOREGROUND_REMOVE)
        stopSelf()
    }

    override fun onDestroy() {
        isRunning = false
        wakeLock?.let {
            if (it.isHeld) it.release()
        }
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null
}
