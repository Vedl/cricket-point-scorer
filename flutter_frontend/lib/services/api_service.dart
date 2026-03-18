import 'dart:convert';
import 'package:http/http.dart' as http;

/// Centralized HTTP client for the Cricket Auction FastAPI backend.
class ApiService {
  // In dev, point to local FastAPI. In prod, update to your deployed URL.
  static const String baseUrl = 'https://cricket-point-scorer.onrender.com';

  // 60-second timeout to handle Render free-tier cold starts (~30-40s)
  static const _timeout = Duration(seconds: 60);

  Future<http.Response> _get(String path) async {
    return http.get(Uri.parse('$baseUrl$path')).timeout(_timeout);
  }

  Future<http.Response> _post(String path, Map<String, dynamic> body) async {
    return http.post(
      Uri.parse('$baseUrl$path'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(body),
    ).timeout(_timeout);
  }

  // ── Authentication ──────────────────────────────────────────
  Future<Map<String, dynamic>> login(String username, String password) async {
    final body = {'username': username, 'password': password};
    final resp = await _post('/auth/login', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> register(String username, String password) async {
    final body = {'username': username, 'password': password};
    final resp = await _post('/auth/register', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Tournaments ──────────────────────────────────────────
  Future<List<Map<String, dynamic>>> getTournaments() async {
    final resp = await _get('/tournaments');
    _checkResponse(resp);
    final data = jsonDecode(resp.body);
    return List<Map<String, dynamic>>.from(data['tournaments']);
  }

  Future<Map<String, dynamic>> createRoom({
    required String adminName,
    required String tournamentType,
    String? userId,
    bool adminPlaying = true,
  }) async {
    final body = {
      'admin_name': adminName,
      'tournament_type': tournamentType,
      'admin_playing': adminPlaying,
      if (userId != null) 'user_id': userId,
    };
    final resp = await _post('/auction/create-room', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> joinRoom({
    required String roomCode,
    required String participantName,
    String? userId,
    String? teamName,
  }) async {
    final body = {
      'room_code': roomCode,
      'participant_name': participantName,
      if (userId != null) 'user_id': userId,
      if (teamName != null) 'team_name': teamName,
    };
    final resp = await _post('/auction/join-room', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getAuctionState(String roomCode) async {
    final resp = await _get('/auction/state?room_code=$roomCode');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Team Claiming ────────────────────────────────────────
  Future<Map<String, dynamic>> claimTeam({
    required String roomCode,
    required String participantName,
    required String teamName,
  }) async {
    final body = {
      'room_code': roomCode,
      'participant_name': participantName,
      'team_name': teamName,
    };
    final resp = await _post('/auction/claim-team', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> claimWithCode({
    required String roomCode,
    required String claimCode,
    required String uid,
  }) async {
    final body = {
      'room_code': roomCode,
      'claim_code': claimCode,
      'uid': uid,
    };
    final resp = await _post('/auction/claim-with-code', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── User Rooms ───────────────────────────────────────────
  Future<Map<String, dynamic>> getUserRooms(String uid) async {
    final resp = await _get('/user/rooms?uid=$uid');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Bidding ──────────────────────────────────────────────
  Future<Map<String, dynamic>> placeBid({
    required String roomCode,
    required String participantName,
    required String playerName,
    required int amount,
  }) async {
    final body = {
      'room_code': roomCode,
      'participant_name': participantName,
      'player_name': playerName,
      'amount': amount,
    };
    final resp = await _post('/auction/bid', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Trading ──────────────────────────────────────────────
  Future<Map<String, dynamic>> proposeTrade({
    required String roomCode,
    required String fromParticipant,
    required String toParticipant,
    required String tradeType,
    String? player,
    String? givePlayer,
    String? getPlayer,
    double price = 0,
  }) async {
    final body = {
      'room_code': roomCode,
      'from_participant': fromParticipant,
      'to_participant': toParticipant,
      'trade_type': tradeType,
      'price': price,
      if (player != null) 'player': player,
      if (givePlayer != null) 'give_player': givePlayer,
      if (getPlayer != null) 'get_player': getPlayer,
    };
    final resp = await _post('/auction/trade/propose', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> respondTrade({
    required String roomCode,
    required String tradeId,
    required String participantName,
    required String action,
  }) async {
    final body = {
      'room_code': roomCode,
      'trade_id': tradeId,
      'participant_name': participantName,
      'action': action,
    };
    final resp = await _post('/auction/trade/respond', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> adminTradeAction({
    required String roomCode,
    required String tradeId,
    required String adminName,
    required String action,
  }) async {
    final body = {
      'room_code': roomCode,
      'trade_id': tradeId,
      'admin_name': adminName,
      'action': action,
    };
    final resp = await _post('/auction/trade/admin-action', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> forceTrade({
    required String roomCode,
    required String adminName,
    required String senderName,
    required String receiverName,
    required String playerName,
    double price = 0,
  }) async {
    final body = {
      'room_code': roomCode,
      'admin_name': adminName,
      'sender_name': senderName,
      'receiver_name': receiverName,
      'player_name': playerName,
      'price': price,
    };
    final resp = await _post('/auction/trade/force', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getTradeLog(String roomCode) async {
    final resp = await _get('/auction/trade-log?room_code=$roomCode');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Admin Controls ───────────────────────────────────────
  Future<Map<String, dynamic>> grantBoost({
    required String roomCode,
    required String adminName,
  }) async {
    final body = {'room_code': roomCode, 'admin_name': adminName};
    final resp = await _post('/auction/boost', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }
  
  Future<Map<String, dynamic>> importCsv({
    required String roomCode,
    required String adminName,
    required String csvText,
  }) async {
    final body = {
      'room_code': roomCode,
      'admin_name': adminName,
      'csv_text': csvText,
    };
    final resp = await _post('/auction/import-csv', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> lockSquads({
    required String roomCode,
    required String adminName,
  }) async {
    final body = {'room_code': roomCode, 'admin_name': adminName};
    final resp = await _post('/auction/lock-squads', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> advanceGameweek({
    required String roomCode,
    required String adminName,
  }) async {
    final body = {'room_code': roomCode, 'admin_name': adminName};
    final resp = await _post('/auction/advance-gameweek', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> calculateScores({
    required String roomCode,
    required String adminName,
    required String cricbuzzUrl,
    int? gameweek,
  }) async {
    final body = {
      'room_code': roomCode,
      'admin_name': adminName,
      'cricbuzz_url': cricbuzzUrl,
      if (gameweek != null) 'gameweek': gameweek,
    };
    final resp = await _post('/auction/calculate-scores', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> importSquads({
    required String roomCode,
    required String adminName,
    required Map<String, dynamic> squads,
  }) async {
    final body = {
      'room_code': roomCode,
      'admin_name': adminName,
      'squads': squads,
    };
    final resp = await _post('/auction/import-squads', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Release Player ───────────────────────────────────────
  Future<Map<String, dynamic>> releasePlayer({
    required String roomCode,
    required String participantName,
    required String playerName,
  }) async {
    final body = {
      'room_code': roomCode,
      'participant_name': participantName,
      'player_name': playerName,
    };
    final resp = await _post('/auction/release-player', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Standings & Schedule ─────────────────────────────────
  Future<Map<String, dynamic>> getStandings(String roomCode, {int? gameweek}) async {
    var url = '/auction/standings?room_code=$roomCode';
    if (gameweek != null) url += '&gameweek=$gameweek';
    final resp = await _get(url);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getSchedule(String roomCode) async {
    final resp = await _get('/auction/schedule?room_code=$roomCode');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  Future<Map<String, dynamic>> getIplSquads() async {
    final resp = await _get('/auction/ipl-squads');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Points Calculator ────────────────────────────────────
  Future<Map<String, dynamic>> calculatePoints(String cricbuzzUrl) async {
    // Note: The /calculate endpoint is a GET or POST. In api_server.py it's a GET or POST depending on definition. 
    // Wait, the python says `app.post("/calculate")`. But it takes URL as a query param.
    // _post expects a body. Let's send an empty body if so.
    final resp = await _post('/calculate?url=${Uri.encodeComponent(cricbuzzUrl)}', {});
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Health ───────────────────────────────────────────────
  Future<Map<String, dynamic>> healthCheck() async {
    final resp = await _get('/health');
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Auction Start ────────────────────────────────────────
  Future<Map<String, dynamic>> startAuction({
    required String roomCode,
    required String adminName,
    double deadlineHours = 24.0,
  }) async {
    final body = {
      'room_code': roomCode,
      'admin_name': adminName,
      'deadline_hours': deadlineHours,
    };
    final resp = await _post('/auction/start', body);
    _checkResponse(resp);
    return jsonDecode(resp.body);
  }

  // ── Helpers ──────────────────────────────────────────────
  void _checkResponse(http.Response resp) {
    if (resp.statusCode >= 400) {
      String detail = 'Request failed';
      try {
        final body = jsonDecode(resp.body);
        detail = body['detail'] ?? detail;
      } catch (_) {}
      throw ApiException(resp.statusCode, detail);
    }
  }
}

class ApiException implements Exception {
  final int statusCode;
  final String message;
  ApiException(this.statusCode, this.message);

  @override
  String toString() => 'ApiException($statusCode): $message';
}
