package `in`.jobrecruitment.gateway

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            val prefs = context.getSharedPreferences("jr_gateway_prefs", Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", "https://sms.jobrecruitment.in") ?: "https://sms.jobrecruitment.in"
            val pairingCode = prefs.getString("pairing_code", "") ?: ""
            val simSlot = prefs.getInt("sim_slot", 0)
            if (pairingCode.isEmpty()) return

            val serviceIntent = Intent(context, SmsGatewayService::class.java).apply {
                action = SmsGatewayService.ACTION_START
                putExtra("server_url", serverUrl)
                putExtra("pairing_code", pairingCode)
                putExtra("sim_slot", simSlot)
            }

            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                context.startForegroundService(serviceIntent)
            } else {
                context.startService(serviceIntent)
            }
        }
    }
}
