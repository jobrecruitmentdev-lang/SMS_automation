package in.jobrecruitment.gateway

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.SharedPreferences
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.os.PowerManager
import android.provider.Settings
import android.telephony.SubscriptionManager
import android.widget.*
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import androidx.core.content.ContextCompat

class MainActivity : AppCompatActivity() {

    private lateinit var etServerUrl: EditText
    private lateinit var etPairingCode: EditText
    private lateinit var spSimSlot: Spinner
    private lateinit var btnToggleService: Button
    private lateinit var tvStatus: TextView
    private lateinit var prefs: SharedPreferences

    private val PERMISSION_REQUEST_CODE = 101
    private var isServiceRunning = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)

        prefs = getSharedPreferences("jr_gateway_prefs", Context.MODE_PRIVATE)

        etServerUrl = findViewById(R.id.etServerUrl)
        etPairingCode = findViewById(R.id.etPairingCode)
        spSimSlot = findViewById(R.id.spSimSlot)
        btnToggleService = findViewById(R.id.btnToggleService)
        tvStatus = findViewById(R.id.tvStatus)

        // Restore saved settings
        etServerUrl.setText(prefs.getString("server_url", "https://sms.jobrecruitment.in"))
        etPairingCode.setText(prefs.getString("pairing_code", "JR-795250"))

        populateSimSlots()
        requestPermissionsIfNeed()
        requestBatteryOptimizationBypass()

        btnToggleService.setOnClickListener {
            if (isServiceRunning) {
                stopGateway()
            } else {
                startGateway()
            }
        }
    }

    private fun populateSimSlots() {
        val simOptions = mutableListOf<String>()
        try {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE) == PackageManager.PERMISSION_GRANTED) {
                val subManager = getSystemService(Context.TELEPHONY_SUBSCRIPTION_SERVICE) as? SubscriptionManager
                val subs = subManager?.activeSubscriptionInfoList
                if (!subs.isNullOrEmpty()) {
                    for (sub in subs) {
                        simOptions.add("SIM ${sub.simSlotIndex + 1}: ${sub.carrierName ?: "Cellular"} (${sub.displayName})")
                    }
                }
            }
        } catch (ignored: Exception) {}

        if (simOptions.isEmpty()) {
            simOptions.add("SIM 1 (Default Cellular SIM)")
            simOptions.add("SIM 2 (Secondary SIM)")
        }

        val adapter = ArrayAdapter(this, android.R.layout.simple_spinner_dropdown_item, simOptions)
        spSimSlot.adapter = adapter
    }

    private fun startGateway() {
        val serverUrl = etServerUrl.text.toString().trim()
        val pairingCode = etPairingCode.text.toString().trim().uppercase()

        if (serverUrl.isEmpty() || pairingCode.isEmpty()) {
            Toast.makeText(this, "Please enter Server URL and Pairing Code", Toast.LENGTH_SHORT).show()
            return
        }

        prefs.edit()
            .putString("server_url", serverUrl)
            .putString("pairing_code", pairingCode)
            .putInt("sim_slot", spSimSlot.selectedItemPosition)
            .apply()

        val intent = Intent(this, SmsGatewayService::class.java).apply {
            action = SmsGatewayService.ACTION_START
            putExtra("server_url", serverUrl)
            putExtra("pairing_code", pairingCode)
            putExtra("sim_slot", spSimSlot.selectedItemPosition)
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            startForegroundService(intent)
        } else {
            startService(intent)
        }

        isServiceRunning = true
        btnToggleService.text = "STOP GATEWAY ENGINE"
        btnToggleService.setBackgroundColor(0xFFE11D48.toInt())
        tvStatus.text = "🟢 Active • Polling Cloud for SMS Campaigns..."
        tvStatus.setTextColor(0xFF10B981.toInt())
    }

    private fun stopGateway() {
        val intent = Intent(this, SmsGatewayService::class.java).apply {
            action = SmsGatewayService.ACTION_STOP
        }
        startService(intent)

        isServiceRunning = false
        btnToggleService.text = "START 24/7 CELLULAR GATEWAY"
        btnToggleService.setBackgroundColor(0xFF0D9488.toInt())
        tvStatus.text = "⚪ Idle (Gateway Stopped)"
        tvStatus.setTextColor(0xFF94A3B8.toInt())
    }

    private fun requestPermissionsIfNeed() {
        val needed = mutableListOf<String>()
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.SEND_SMS) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.SEND_SMS)
        }
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.READ_PHONE_STATE) != PackageManager.PERMISSION_GRANTED) {
            needed.add(Manifest.permission.READ_PHONE_STATE)
        }
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            if (ContextCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) != PackageManager.PERMISSION_GRANTED) {
                needed.add(Manifest.permission.POST_NOTIFICATIONS)
            }
        }
        if (needed.isNotEmpty()) {
            ActivityCompat.requestPermissions(this, needed.toTypedArray(), PERMISSION_REQUEST_CODE)
        }
    }

    private fun requestBatteryOptimizationBypass() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.M) {
            val powerManager = getSystemService(Context.POWER_SERVICE) as PowerManager
            if (!powerManager.isIgnoringBatteryOptimizations(packageName)) {
                try {
                    val intent = Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS).apply {
                        data = Uri.parse("package:$packageName")
                    }
                    startActivity(intent)
                } catch (ignored: Exception) {}
            }
        }
    }

    override fun onRequestPermissionsResult(requestCode: Int, permissions: Array<out String>, grantResults: IntArray) {
        super.onRequestPermissionsResult(requestCode, permissions, grantResults)
        populateSimSlots()
    }
}
