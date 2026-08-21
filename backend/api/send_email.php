<?php
/**
 * JobRecruitment.in — Production Hostinger PHP Mailer Bridge
 * Endpoint: POST https://jobrecruitment.in/backend/api/send_email.php
 * Role: Dispatches HTML verification emails via hire@jobrecruitment.in on Hostinger Localhost
 */

header('Content-Type: application/json; charset=utf-8');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: POST, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type, Authorization, X-API-Key');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

// 1. Authenticate Request
$authHeader = $_SERVER['HTTP_AUTHORIZATION'] ?? $_SERVER['REDIRECT_HTTP_AUTHORIZATION'] ?? $_SERVER['HTTP_X_API_KEY'] ?? '';
$expectedKey = 'jrk_a537e025205460bf1da0ec9765a0e192d2a33b6c773fbdaa';

if (!empty($authHeader) && strpos($authHeader, 'Bearer ') === 0) {
    $token = substr($authHeader, 7);
} else {
    $token = $authHeader;
}

if (empty($token) || $token !== $expectedKey) {
    http_response_code(401);
    echo json_encode(['ok' => false, 'error' => 'Unauthorized: Invalid API Key']);
    exit;
}

// 2. Parse JSON Payload
$input = file_get_contents('php://input');
$data = json_decode($input, true);

if (!$data || empty($data['to']) || empty($data['subject']) || empty($data['html'])) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Missing required fields: to, subject, html']);
    exit;
}

$to = filter_var(trim($data['to']), FILTER_SANITIZE_EMAIL);
if (!filter_var($to, FILTER_VALIDATE_EMAIL)) {
    http_response_code(400);
    echo json_encode(['ok' => false, 'error' => 'Invalid destination email address']);
    exit;
}

$subject = $data['subject'];
$htmlBody = $data['html'];
$fromName = $data['from_name'] ?? 'JobRecruitment AI SMS Studio';
$fromEmail = 'hire@jobrecruitment.in';

// 3. Construct Standard RFC 2822 MIME Headers
$headers = [];
$headers[] = 'MIME-Version: 1.0';
$headers[] = 'Content-type: text/html; charset=utf-8';
$headers[] = 'From: ' . $fromName . ' <' . $fromEmail . '>';
$headers[] = 'Reply-To: support@jobrecruitment.in';
$headers[] = 'X-Mailer: PHP/' . phpversion();
$headers[] = 'X-Priority: 1 (Highest)';

// 4. Send Email via Hostinger Localhost Mail Server
$mailSent = @mail($to, $subject, $htmlBody, implode("\r\n", $headers));

if ($mailSent) {
    echo json_encode([
        'ok' => true,
        'message' => "Verification email delivered to {$to} via Hostinger PHP Mailer.",
        'timestamp' => date('c')
    ]);
} else {
    http_response_code(500);
    echo json_encode([
        'ok' => false,
        'error' => 'Hostinger mail() server could not dispatch email.',
        'timestamp' => date('c')
    ]);
}
