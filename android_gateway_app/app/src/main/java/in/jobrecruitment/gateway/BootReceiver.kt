package in.jobrecruitment.gateway

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.Build

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent?) {
        if (intent?.action == Intent.ACTION_BOOT_COMPLETED) {
            val prefs = context.getSharedPreferences("jr_gateway_prefs", Context.MODE_PRIVATE)
            val serverUrl = prefs.getString("server_url", "https://sms-automation-q1zf.onrender.com") ?: return
            val pairingCode = prefs.getString("pairing_code", "JR-100001") ?: return
            val simSlot = prefs.getInt("sim_slot", 0)

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
