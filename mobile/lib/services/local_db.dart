import 'dart:convert';
import 'package:sqflite/sqflite.dart';
import 'package:path/path.dart';

class LocalDB {
  static final LocalDB instance = LocalDB._();
  Database? _db;

  LocalDB._();

  Future<void> init() async {
    final dbPath = await getDatabasesPath();
    _db = await openDatabase(
      join(dbPath, 'sports_app.db'),
      version: 1,
      onCreate: (db, version) async {
        await db.execute('''
          CREATE TABLE fixtures (
            match_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at INTEGER NOT NULL
          )
        ''');
        await db.execute('''
          CREATE TABLE standings (
            league_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at INTEGER NOT NULL
          )
        ''');
        await db.execute('''
          CREATE TABLE clubs (
            club_id TEXT PRIMARY KEY,
            data TEXT NOT NULL,
            cached_at INTEGER NOT NULL
          )
        ''');
        await db.execute('''
          CREATE TABLE pending_actions (
            action_id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            payload TEXT NOT NULL,
            queued_at TEXT NOT NULL,
            base_version INTEGER NOT NULL,
            status TEXT DEFAULT 'pending'
          )
        ''');
      },
    );
  }

  Database get db => _db!;

  // ── Fixtures ─────────────────────────────────────────
  Future<void> cacheFixtures(List<dynamic> fixtures) async {
    final batch = db.batch();
    for (final fx in fixtures) {
      batch.insert('fixtures', {
        'match_id': fx['match_id'],
        'data': jsonEncode(fx),
        'cached_at': DateTime.now().millisecondsSinceEpoch,
      }, conflictAlgorithm: ConflictAlgorithm.replace);
    }
    await batch.commit(noResult: true);
  }

  Future<List<Map<String, dynamic>>> getCachedFixtures() async {
    final rows = await db.query('fixtures', orderBy: 'cached_at DESC');
    return rows.map((r) => jsonDecode(r['data'] as String) as Map<String, dynamic>).toList();
  }

  // ── Standings ─────────────────────────────────────────
  Future<void> cacheStandings(String leagueId, Map<String, dynamic> data) async {
    await db.insert('standings', {
      'league_id': leagueId,
      'data': jsonEncode(data),
      'cached_at': DateTime.now().millisecondsSinceEpoch,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<Map<String, dynamic>?> getCachedStandings(String leagueId) async {
    final rows = await db.query('standings', where: 'league_id = ?', whereArgs: [leagueId]);
    if (rows.isEmpty) return null;
    return jsonDecode(rows.first['data'] as String) as Map<String, dynamic>;
  }

  // ── Clubs ─────────────────────────────────────────────
  Future<void> cacheClub(String clubId, Map<String, dynamic> data) async {
    await db.insert('clubs', {
      'club_id': clubId,
      'data': jsonEncode(data),
      'cached_at': DateTime.now().millisecondsSinceEpoch,
    }, conflictAlgorithm: ConflictAlgorithm.replace);
  }

  Future<Map<String, dynamic>?> getCachedClub(String clubId) async {
    final rows = await db.query('clubs', where: 'club_id = ?', whereArgs: [clubId]);
    if (rows.isEmpty) return null;
    return jsonDecode(rows.first['data'] as String) as Map<String, dynamic>;
  }

  // ── Pending Actions ───────────────────────────────────
  Future<void> queueAction({
    required String actionId,
    required String type,
    required Map<String, dynamic> payload,
    required String queuedAt,
    required int baseVersion,
  }) async {
    await db.insert('pending_actions', {
      'action_id': actionId,
      'type': type,
      'payload': jsonEncode(payload),
      'queued_at': queuedAt,
      'base_version': baseVersion,
      'status': 'pending',
    }, conflictAlgorithm: ConflictAlgorithm.ignore);
  }

  Future<List<Map<String, dynamic>>> getPendingActions() async {
    final rows = await db.query(
      'pending_actions',
      where: 'status = ?',
      whereArgs: ['pending'],
      orderBy: 'queued_at ASC',
    );
    return rows.map((r) => {
      'action_id': r['action_id'],
      'type': r['type'],
      'payload': jsonDecode(r['payload'] as String),
      'queued_at': r['queued_at'],
      'base_version': r['base_version'],
    }).toList();
  }

  Future<void> markActionSynced(String actionId, String status) async {
    await db.update(
      'pending_actions',
      {'status': status},
      where: 'action_id = ?',
      whereArgs: [actionId],
    );
  }

  Future<void> clearSyncedActions() async {
    await db.delete('pending_actions', where: 'status != ?', whereArgs: ['pending']);
  }
}
