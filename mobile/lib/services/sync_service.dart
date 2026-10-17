import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:uuid/uuid.dart';
import 'api_service.dart';
import 'local_db.dart';

enum SyncStatus { idle, syncing, online, offline }

class SyncService extends ChangeNotifier {
  SyncStatus _status = SyncStatus.idle;
  List<Map<String, dynamic>> _pendingActions = [];
  List<Map<String, dynamic>> _syncResults = [];

  SyncStatus get status => _status;
  List<Map<String, dynamic>> get pendingActions => _pendingActions;
  List<Map<String, dynamic>> get syncResults => _syncResults;
  int get pendingCount => _pendingActions.length;

  Future<void> loadPending() async {
    _pendingActions = await LocalDB.instance.getPendingActions();
    notifyListeners();
  }

  Future<void> queueScoreAction({
    required String matchId,
    required String eventId,
    required String teamId,
    required String eventType,
    required int baseVersion,
  }) async {
    final actionId = const Uuid().v4();
    final queuedAt = DateTime.now().toUtc().toIso8601String();
    final payload = {
      'event_id': eventId,
      'match_id': matchId,
      'type': 'score',
      'payload': {'team_id': teamId, 'event_type': eventType},
    };
    await LocalDB.instance.queueAction(
      actionId: actionId, type: 'score_event',
      payload: payload, queuedAt: queuedAt, baseVersion: baseVersion,
    );
    await loadPending();
  }

  Future<void> queueRosterAction({
    required Map<String, dynamic> transferPayload,
    required int baseVersion,
  }) async {
    final actionId = const Uuid().v4();
    final queuedAt = DateTime.now().toUtc().toIso8601String();
    await LocalDB.instance.queueAction(
      actionId: actionId, type: 'roster_transfer',
      payload: transferPayload, queuedAt: queuedAt, baseVersion: baseVersion,
    );
    await loadPending();
  }

  Future<void> sync(ApiService api, String deviceId) async {
    _status = SyncStatus.syncing;
    notifyListeners();

    try {
      final pending = await LocalDB.instance.getPendingActions();
      if (pending.isEmpty) {
        _status = SyncStatus.online;
        notifyListeners();
        return;
      }

      final actions = pending.map((a) => {
        'action_id': a['action_id'],
        'type': a['type'],
        'queued_at': a['queued_at'],
        'base_version': a['base_version'],
        'payload': a['payload'],
      }).toList();

      final result = await api.post('/audit/v1/offline-sync', {
        'device_id': deviceId,
        'actions': actions,
      });

      _syncResults = List<Map<String, dynamic>>.from(result['results'] ?? []);

      for (final r in _syncResults) {
        final status = r['status'] as String;
        await LocalDB.instance.markActionSynced(r['action_id'], status);
      }

      await loadPending();
      _status = SyncStatus.online;
    } catch (e) {
      _status = SyncStatus.offline;
    }
    notifyListeners();
  }
}
