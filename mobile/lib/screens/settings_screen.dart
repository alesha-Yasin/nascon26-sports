import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'package:shared_preferences/shared_preferences.dart';
import '../services/api_service.dart';
import '../widgets/sync_indicator.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});
  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late TextEditingController _urlCtrl;

  @override
  void initState() {
    super.initState();
    final api = context.read<ApiService>();
    _urlCtrl = TextEditingController(text: api.baseUrl);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings'), actions: const [SyncIndicator()]),
      body: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Text('Server URL', style: TextStyle(fontWeight: FontWeight.bold)),
          const SizedBox(height: 8),
          TextField(
            controller: _urlCtrl,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              helperText: 'Emulator: http://10.0.2.2:8080 | Device: http://<LAN-IP>:8080',
            ),
          ),
          const SizedBox(height: 16),
          SizedBox(
            width: double.infinity,
            child: ElevatedButton(
              onPressed: () async {
                final api = context.read<ApiService>();
                api.setBaseUrl(_urlCtrl.text.trim());
                final prefs = await SharedPreferences.getInstance();
                await prefs.setString('base_url', _urlCtrl.text.trim());
                if (context.mounted) {
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(content: Text('Server URL saved!'), backgroundColor: Colors.green),
                  );
                }
              },
              child: const Text('Save'),
            ),
          ),
        ]),
      ),
    );
  }
}
