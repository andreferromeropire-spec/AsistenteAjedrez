const PIECE_NAMES = {
  p: 'Peón', n: 'Caballo', b: 'Alfil', r: 'Torre', q: 'Dama', k: 'Rey'
}

const PROFILES = {
  small: {
    fontSize: '18px',
    boardSize: 560,
    btnPadding: '16px 24px',
    btnFontSize: '1.15em'
  },
  standard: {
    fontSize: '15px',
    boardSize: 480,
    btnPadding: '10px 20px',
    btnFontSize: '1em'
  },
  comfort: {
    fontSize: '18px',
    boardSize: 480,
    btnPadding: '14px 22px',
    btnFontSize: '1.1em'
  }
}

const TRANSLATIONS = {
  es: {
    loading: 'Cargando puzzles...',
    progressLabel: function(i, total) { return 'Ejercicio ' + i + ' de ' + total },
    rivalMove: function(piece, from, to) { return 'El rival jugó ' + piece + ' de ' + from + ' a ' + to + '. Observá la jugada.' },
    scanSectors: [
      '① Flanco de dama (a-c) — ¿hay piezas sin defensor?',
      '② Centro (d-e) — ¿hay piezas sin defensor?',
      '③ Flanco de rey (f-h) — ¿hay piezas sin defensor?'
    ],
    markingTitle: 'Marcá todas las piezas sin defensor — de cualquier color.',
    markingSubtitle: 'Una pieza está indefensa si ninguna pieza propia la protege.',
    legendHanging: '● Pieza colgada: atacada sin ningún defensor',
    legendVulnerable: '● Pieza vulnerable: sin defensor, no atacada aún',
    btnNoDefenders: 'No hay ninguna',
    btnConfirm: function(n) { return 'Confirmar (' + n + ' marcadas)' },
    feedbackCorrect: '✓ Correcto',
    feedbackWrong: '✗ Revisá el tablero',
    stayButton: 'Quedarme viendo',
    nextButton: 'Siguiente →',
    btnNext: 'Siguiente →',
    btnUnderstood: 'Comprendido, siguiente',
    fpExplanation: 'Marcaste piezas que sí estaban defendidas',
    defendedBy: 'defendida por',
    on: 'en',
    sessionCompleted: 'Sesión completada',
    loadingResults: 'Cargando resultados...',
    summaryExercises: 'Ejercicios',
    summaryCorrect: 'Correctos',
    summaryAccuracy: 'Precisión',
    summaryAvgTime: 'Tiempo promedio',
    summarySectorWeak: '📍 Sector más débil:',
    summarySectorHint: 'Prestale atención especial la próxima vez.',
    summaryScanTime: '⏱ Tiempo promedio de escaneo:',
    summaryFpWarningTitle: '⚠ Marcaste piezas defendidas con frecuencia.',
    summaryFpWarningHint: 'Antes de marcar, verificá quién defiende la pieza.',
    summaryTransfer: '→ En tu próxima partida: escaneá los tres sectores antes de mover.',
    btnNewSession: 'Nueva sesión',
    sectorNames: { 'flanco de dama': 'flanco de dama', 'centro': 'centro', 'flanco de rey': 'flanco de rey' },
    pieceNameEn: null,
    explanationMissing: function(items) { return 'Te faltaron marcar: ' + items.join(', ') },
    explanationFalsePositives: function(items) { return 'Marcaste de más: ' + items.join(', ') },
    explanationCorrect: 'Correcto.',
    homeTitle: 'Entrenador Táctico',
    homeSubtitle: 'Aprendé a escanear el tablero antes de mover.',
    btnNewRound: 'Nueva Ronda',
    btnHowToPlay: 'Cómo jugar',
    btnWhyThis: '¿Para qué sirve?',
    btnBack: '← Volver',
    btnBackHome: '← Menú principal',
    btnExitTraining: '✕ Salir',
    htpTitle: 'Cómo jugar',
    htpContent: '<p>Se te muestra una posición después de que el rival hizo su jugada.</p><p>Tu tarea: <strong>encontrar todas las piezas sin defensor</strong> antes de mover.</p><h4>¿Qué es una pieza sin defensor?</h4><p><span style="color:#E05C5C">● Colgada</span>: está siendo atacada por el rival Y ninguna pieza propia la defiende. Si el rival la captura, la perdés.</p><p><span style="color:#F6D860">● Vulnerable</span>: ninguna pieza propia la defiende, pero tampoco está siendo atacada todavía. Es un blanco potencial.</p><h4>El escaneo</h4><p>Antes de marcar, el tablero te guía por tres sectores: flanco de dama (a-c), centro (d-e) y flanco de rey (f-h). Mirá cada uno con atención.</p><h4>Cómo marcar</h4><p>Hacé clic sobre las piezas que creés que están sin defensor. Podés desmarcar clickeando de nuevo. Cuando estés listo, confirmá.</p>',
    whyTitle: '¿Para qué sirve?',
    whyContent: '<p>La mayoría de las piezas se pierden no por cálculo sino por <strong>no ver</strong> que estaban en peligro.</p><p>Este entrenador te ayuda a desarrollar el hábito de <strong>escanear el tablero completo</strong> antes de mover — igual que los jugadores de alto nivel.</p><p>Con práctica regular vas a empezar a notar automáticamente qué piezas están expuestas, tanto las tuyas como las del rival.</p><p>Los puzzles vienen de la base de datos de Lichess y están filtrados por dificultad para tu nivel.</p>',
    exitConfirm: '¿Salir del entrenamiento? Se perderá el progreso de esta ronda.',
    summaryBtnNewRound: 'Nueva Ronda',
    summaryBtnHome: 'Menú principal',
    scanTimeTooFast: function(s) { return '⚡ Escaneaste en ' + s + 's — intentá tomarte al menos 4s' },
    scanTimeGood: function(s) { return '⏱ Buen tiempo de escaneo: ' + s + 's' },
    scanTimeDetailed: function(s) { return '⏱ Escaneo muy detallado: ' + s + 's — bien hecho' },
    historyLastSession: 'Última sesión:',
    historyBestSession: 'Mejor sesión:',
    historyTotalSessions: 'Sesiones totales:',
    historyImproved: function(pct) { return '📈 Mejoraste un ' + pct + '% desde la última vez' },
    sectorIndicator: function(i, total) { return 'Sector ' + i + '/' + total },
    transferDynamic: { queenside: '→ En tu próxima partida: prestá atención especial al flanco de dama.', center: '→ En tu próxima partida: revisá bien el centro.', kingside: '→ En tu próxima partida: no te olvides del flanco de rey.', none: '→ En tu próxima partida: escaneá los tres sectores antes de mover.' },
    transferQuestion: '¿Cuántas piezas perdiste sin querer en tu última partida?',
    transferResponseZero: '👏 Excelente. Seguí escaneando antes de mover.',
    transferResponseOne: '👍 Uno es manejable. El escaneo te va a ayudar a bajarlo a cero.',
    transferResponseTwo: 'Dos piezas — el escaneo sistemático es exactamente para esto.',
    transferResponseMore: 'Muchas. Hacé el escaneo de los tres sectores antes de cada jugada.',
    timerHide: 'Ocultar',
    timerShow: 'Mostrar',
    levelSelectorTitle: 'Nivel de dificultad',
    levelBeginner: 'Principiante',
    levelIntermediate: 'Intermedio',
    levelAdvanced: 'Avanzado',
    levelDescBeginner: '1 pieza sin defensor',
    levelDescIntermediate: '2-3 piezas sin defensor',
    levelDescAdvanced: '4+ piezas sin defensor',
    levelStatsSuffix: function(acc, time) { return acc + '% · ' + time + 's promedio' },
    levelNoStats: 'Sin sesiones aún',
    suggestionUp: function(level) { return '📈 Estás encontrando bien las piezas. ¿Querés probar ' + level + '?' },
    suggestionDown: function(level) { return '📉 Este nivel es desafiante. ¿Querés probar ' + level + '?' },
    suggestionYes: 'Sí, probar',
    suggestionStay: 'Quedarme aquí',
    progressWithLevel: function(i, total, levelName) { return 'Ejercicio ' + i + ' de ' + total + '  ·  ' + levelName },
    profileLabel: 'Visualización:',
    profileSmall: '🐣 Pequeños',
    profileStandard: '👤 Estándar',
    profileComfort: '👓 Cómodo',
    streakLabel: 'seguidos',
    summaryMaxStreak: 'Mejor racha de la sesión'
  },
  en: {
    loading: 'Loading puzzles...',
    progressLabel: function(i, total) { return 'Exercise ' + i + ' of ' + total },
    rivalMove: function(piece, from, to) { return 'Opponent played ' + piece + ' from ' + from + ' to ' + to + '. Observe the move.' },
    scanSectors: [
      '① Queenside (a–c) — are there undefended pieces?',
      '② Center (d–e) — are there undefended pieces?',
      '③ Kingside (f–h) — are there undefended pieces?'
    ],
    markingTitle: 'Mark all pieces without a defender — any color.',
    markingSubtitle: 'A piece is undefended if no friendly piece protects it.',
    legendHanging: '● Hanging piece: attacked with no defender',
    legendVulnerable: '● Vulnerable piece: no defender, not attacked yet',
    btnNoDefenders: 'None',
    btnConfirm: function(n) { return 'Confirm (' + n + ' marked)' },
    feedbackCorrect: '✓ Correct',
    feedbackWrong: '✗ Review the board',
    stayButton: 'Stay on this position',
    nextButton: 'Next →',
    btnNext: 'Next →',
    btnUnderstood: 'Got it, next',
    fpExplanation: 'You marked pieces that were defended',
    defendedBy: 'defended by',
    on: 'on',
    sessionCompleted: 'Session completed',
    loadingResults: 'Loading results...',
    summaryExercises: 'Exercises',
    summaryCorrect: 'Correct',
    summaryAccuracy: 'Accuracy',
    summaryAvgTime: 'Average time',
    summarySectorWeak: '📍 Weakest sector:',
    summarySectorHint: 'Pay extra attention there next time.',
    summaryScanTime: '⏱ Average scan time:',
    summaryFpWarningTitle: '⚠ You often marked defended pieces.',
    summaryFpWarningHint: 'Before marking, check which piece is defending it.',
    summaryTransfer: '→ In your next game: scan all three sectors before you move.',
    btnNewSession: 'New session',
    sectorNames: { 'flanco de dama': 'queenside', 'centro': 'center', 'flanco de rey': 'kingside' },
    pieceNameEn: { Peón: 'Pawn', Caballo: 'Knight', Alfil: 'Bishop', Torre: 'Rook', Dama: 'Queen', Rey: 'King' },
    explanationMissing: function(items) { return 'You missed: ' + items.join(', ') },
    explanationFalsePositives: function(items) { return 'You marked extra: ' + items.join(', ') },
    explanationCorrect: 'Correct.',
    homeTitle: 'Tactical Trainer',
    homeSubtitle: 'Learn to scan the board before you move.',
    btnNewRound: 'New Round',
    btnHowToPlay: 'How to play',
    btnWhyThis: 'What is this for?',
    btnBack: '← Back',
    btnBackHome: '← Main menu',
    btnExitTraining: '✕ Exit',
    htpTitle: 'How to play',
    htpContent: '<p>You are shown a position after the opponent made their move.</p><p>Your task: <strong>find all undefended pieces</strong> before moving.</p><h4>What is an undefended piece?</h4><p><span style="color:#E05C5C">● Hanging</span>: it is being attacked by the opponent AND no friendly piece defends it. If the opponent captures it, you lose it.</p><p><span style="color:#F6D860">● Vulnerable</span>: no friendly piece defends it, but it is not under attack yet. It is a potential target.</p><h4>Scanning</h4><p>Before marking, the board guides you through three sectors: queenside (a–c), center (d–e), and kingside (f–h). Look at each one carefully.</p><h4>How to mark</h4><p>Click on the pieces you think are undefended. You can unmark by clicking again. When you are ready, confirm.</p>',
    whyTitle: 'What is this for?',
    whyContent: '<p>Most pieces are lost not by miscalculation but by <strong>failing to see</strong> they were in danger.</p><p>This trainer helps you develop the habit of <strong>scanning the full board</strong> before you move — just like strong players.</p><p>With regular practice you will start to notice automatically which pieces are exposed, both yours and your opponent\'s.</p><p>Puzzles come from the Lichess database and are filtered by difficulty for your level.</p>',
    exitConfirm: 'Exit training? Progress for this round will be lost.',
    summaryBtnNewRound: 'New Round',
    summaryBtnHome: 'Main menu',
    scanTimeTooFast: function(s) { return '⚡ You scanned in ' + s + 's — try to take at least 4s' },
    scanTimeGood: function(s) { return '⏱ Good scan time: ' + s + 's' },
    scanTimeDetailed: function(s) { return '⏱ Very thorough scan: ' + s + 's — well done' },
    historyLastSession: 'Last session:',
    historyBestSession: 'Best session:',
    historyTotalSessions: 'Total sessions:',
    historyImproved: function(pct) { return '📈 You improved ' + pct + '% since last time' },
    sectorIndicator: function(i, total) { return 'Sector ' + i + '/' + total },
    transferDynamic: { queenside: '→ Next game: pay special attention to the queenside.', center: '→ Next game: make sure to check the center.', kingside: "→ Next game: don't forget the kingside.", none: '→ Next game: scan all three sectors before you move.' },
    transferQuestion: 'How many pieces did you lose by accident in your last game?',
    transferResponseZero: '👏 Excellent. Keep scanning before you move.',
    transferResponseOne: '👍 One is manageable. Scanning will help you get to zero.',
    transferResponseTwo: 'Two pieces — systematic scanning is exactly for this.',
    transferResponseMore: 'Several. Scan all three sectors before every move.',
    timerHide: 'Hide',
    timerShow: 'Show',
    levelSelectorTitle: 'Difficulty level',
    levelBeginner: 'Beginner',
    levelIntermediate: 'Intermediate',
    levelAdvanced: 'Advanced',
    levelDescBeginner: '1 undefended piece',
    levelDescIntermediate: '2-3 undefended pieces',
    levelDescAdvanced: '4+ undefended pieces',
    levelStatsSuffix: function(acc, time) { return acc + '% · ' + time + 's avg' },
    levelNoStats: 'No sessions yet',
    suggestionUp: function(level) { return "📈 You're doing well at this level. Want to try " + level + '?' },
    suggestionDown: function(level) { return '📉 This level is challenging. Want to try ' + level + '?' },
    suggestionYes: 'Yes, try it',
    suggestionStay: 'Stay here',
    progressWithLevel: function(i, total, levelName) { return 'Exercise ' + i + ' of ' + total + '  ·  ' + levelName },
    profileLabel: 'Display:',
    profileSmall: '🐣 Young learners',
    profileStandard: '👤 Standard',
    profileComfort: '👓 Comfort',
    streakLabel: 'in a row',
    summaryMaxStreak: 'Best streak this session'
  }
}

function t(key) {
  var lang = sessionState.lang || 'es'
  var dict = TRANSLATIONS[lang] || TRANSLATIONS.es
  return dict[key]
}

let board = null
let game = new Chess()
function getHistoryByLevel() {
  var raw = '{}'
  try { raw = window.localStorage.getItem('trainer_history') || '{}' } catch (e) {}
  var history = {}
  try {
    history = JSON.parse(raw)
    if (Array.isArray(history)) {
      history = { beginner: history }
      try { window.localStorage.setItem('trainer_history', JSON.stringify(history)) } catch (e2) {}
    }
  } catch (e) {}
  return history
}

function getLevelStats(level) {
  var history = getHistoryByLevel()
  var sessions = history[level] || []
  if (!sessions.length) return null
  var avgAccuracy = sessions.reduce(function(s, x) { return s + x.accuracy }, 0) / sessions.length
  var withTime = sessions.filter(function(x) { return x.avgTime != null })
  var avgTime = withTime.length ? withTime.reduce(function(s, x) { return s + x.avgTime }, 0) / withTime.length : 0
  return {
    avgAccuracy: Math.round(avgAccuracy),
    avgTime: avgTime.toFixed(1),
    total: sessions.length
  }
}

function checkLevelSuggestion(level) {
  var history = getHistoryByLevel()
  var sessions = (history[level] || []).slice(-3)
  if (sessions.length < 3) return null
  var avgAcc = sessions.reduce(function(s, x) { return s + x.accuracy }, 0) / sessions.length
  if (avgAcc >= 80 && level !== 'advanced') return { direction: 'up', nextLevel: level === 'beginner' ? 'intermediate' : 'advanced' }
  if (avgAcc <= 40 && level !== 'beginner') return { direction: 'down', nextLevel: level === 'advanced' ? 'intermediate' : 'beginner' }
  return null
}

function levelLabel(level) {
  if (level === 'intermediate') return t('levelIntermediate')
  if (level === 'advanced') return t('levelAdvanced')
  return t('levelBeginner')
}

let sessionState = {
  sessionId: null,
  puzzleIndex: 0,
  totalPuzzles: 10,
  currentPuzzle: null,
  markedSquares: [],
  phase: 'loading',
  lang: 'es',
  lastResult: null,
  currentScreen: 'home',
  selectedLevel: 'beginner',
  level: 'beginner',
  clicksEnabled: false,
  profile: 'standard',
  soundEnabled: true,
  streak: 0,
  maxStreak: 0
}

function applyProfile(key) {
  var p = PROFILES[key] || PROFILES.standard
  document.documentElement.style.setProperty('--font-size-base', p.fontSize)
  document.documentElement.style.setProperty('--btn-padding', p.btnPadding)
  document.documentElement.style.setProperty('--btn-font-size', p.btnFontSize)
  sessionState.profile = key
  try { window.localStorage.setItem('trainer_profile', key) } catch (e) {}
  var wrapper = document.getElementById('board-wrapper')
  if (wrapper) {
    var w = window.innerWidth
    var size = (w <= 767) ? Math.min(w, w - 0) : Math.min(p.boardSize, w - 32)
    if (w <= 767) wrapper.style.width = '100%'
    else wrapper.style.width = size + 'px'
    if (board) {
      setTimeout(function() {
        board.resize()
        if (sessionState.currentPuzzle) {
          board.position(sessionState.currentPuzzle.fen, false)
        }
      }, 50)
    }
  }
  updateProfileButtons()
}

function updateProfileButtons() {
  var key = sessionState.profile || 'standard'
  $('#profile-selector .profile-btn').removeClass('profile-btn-active').each(function() {
    if ($(this).data('profile') === key) $(this).addClass('profile-btn-active')
  })
  $('#profile-selector #profile-label').text(t('profileLabel'))
  $('#profile-selector .profile-btn[data-profile="small"]').text(t('profileSmall'))
  $('#profile-selector .profile-btn[data-profile="standard"]').text(t('profileStandard'))
  $('#profile-selector .profile-btn[data-profile="comfort"]').text(t('profileComfort'))
  $('#profile-overlay .profile-btn[data-profile="small"]').text(t('profileSmall'))
  $('#profile-overlay .profile-btn[data-profile="standard"]').text(t('profileStandard'))
  $('#profile-overlay .profile-btn[data-profile="comfort"]').text(t('profileComfort'))
  $('#profile-overlay .profile-btn').removeClass('profile-btn-active').each(function() {
    if ($(this).data('profile') === key) $(this).addClass('profile-btn-active')
  })
  $('#profile-overlay-title').text(t('profileLabel'))
}

function showScreen(name) {
  $('.screen').hide()
  $('#screen-' + name).show()
  sessionState.currentScreen = name
}

function renderHomeTexts() {
  var level = 'beginner'
  try { level = window.localStorage.getItem('trainer_level') || 'beginner' } catch (e) {}
  if (level !== 'beginner' && level !== 'intermediate' && level !== 'advanced') level = 'beginner'
  sessionState.selectedLevel = level

  $('#home-title').text(t('homeTitle'))
  $('#home-subtitle').text(t('homeSubtitle'))
  $('#btn-new-round').html('🎯 ' + t('btnNewRound'))
  $('#btn-how-to-play').html('📖 ' + t('btnHowToPlay'))
  $('#btn-why-this').html('❓ ' + t('btnWhyThis'))
  updateProfileButtons()

  var suggestion = checkLevelSuggestion(level)
  var dismissed = false
  try { dismissed = window.localStorage.getItem('trainer_level_suggestion_dismissed_' + level) === 'true' } catch (e) {}
  var $banner = $('#level-suggestion-banner')
  if (suggestion && !dismissed) {
    var nextLabel = levelLabel(suggestion.nextLevel)
    var msg = suggestion.direction === 'up' ? t('suggestionUp')(nextLabel) : t('suggestionDown')(nextLabel)
    $banner.html(
      '<p style="margin:0 0 8px 0">' + msg + '</p>' +
      '<div style="display:flex; gap:8px; flex-wrap:wrap">' +
      '<button type="button" class="btn-suggestion-yes btn-primary" style="padding:8px 16px; font-size:0.9em">' + t('suggestionYes') + '</button>' +
      '<button type="button" class="btn-suggestion-stay btn-secondary" style="padding:8px 16px; font-size:0.9em">' + t('suggestionStay') + '</button>' +
      '</div>'
    ).show()
    $banner.off('click').on('click', '.btn-suggestion-yes', function() {
      sessionState.selectedLevel = suggestion.nextLevel
      try { window.localStorage.setItem('trainer_level', suggestion.nextLevel) } catch (e) {}
      $banner.hide()
      renderHomeTexts()
    })
    $banner.on('click', '.btn-suggestion-stay', function() {
      try { window.localStorage.setItem('trainer_level_suggestion_dismissed_' + level, 'true') } catch (e) {}
      $banner.hide()
    })
  } else {
    $banner.hide()
  }

  var levels = ['beginner', 'intermediate', 'advanced']
  var levelNames = [t('levelBeginner'), t('levelIntermediate'), t('levelAdvanced')]
  var levelDescs = [t('levelDescBeginner'), t('levelDescIntermediate'), t('levelDescAdvanced')]
  var selHtml = '<p class="level-selector-title">' + t('levelSelectorTitle') + '</p>'
  levels.forEach(function(lv, idx) {
    var stats = getLevelStats(lv)
    var statsHtml = stats ? t('levelStatsSuffix')(stats.avgAccuracy, stats.avgTime) : t('levelNoStats')
    selHtml += '<div class="level-option' + (lv === sessionState.selectedLevel ? ' level-option-active' : '') + '" data-level="' + lv + '">'
    selHtml += '<span class="level-name">' + levelNames[idx] + '</span>'
    selHtml += '<span class="level-desc">' + levelDescs[idx] + '</span>'
    selHtml += '<span class="level-stats">' + statsHtml + '</span>'
    selHtml += '</div>'
  })
  $('#level-selector').html(selHtml).show()
  $('#profile-selector').show()
  $(document).off('click', '#level-selector .level-option').on('click', '#level-selector .level-option', function() {
    var lv = $(this).data('level')
    sessionState.selectedLevel = lv
    try { window.localStorage.setItem('trainer_level', lv) } catch (e) {}
    $('#level-selector .level-option').removeClass('level-option-active')
    $(this).addClass('level-option-active')
  })

  var sessions = (getHistoryByLevel()[sessionState.selectedLevel] || [])
  var $hist = $('#home-history')
  if (!sessions.length) {
    $hist.empty().hide()
    return
  }
  var last = sessions[sessions.length - 1]
  var best = sessions.reduce(function(acc, h) {
    return (h.correct / h.total) > (acc.correct / acc.total) ? h : acc
  }, last)
  var html = ''
  html += '<span class="history-row">' + t('historyLastSession') + ' ' + last.correct + '/' + last.total + ' ✓ (' + last.accuracy + '%)</span>'
  html += '<span class="history-row">' + t('historyBestSession') + ' ' + best.correct + '/' + best.total + ' ✓ (' + best.accuracy + '%)</span>'
  html += '<span class="history-row">' + t('historyTotalSessions') + ' ' + sessions.length + '</span>'
  if (sessions.length >= 3) {
    var prev = sessions[sessions.length - 2]
    var diff = last.accuracy - prev.accuracy
    if (diff > 0) {
      html += '<span class="history-improved history-row">' + t('historyImproved')(diff) + '</span>'
    }
  }
  $hist.html(html).show()
}

function renderInfoScreen(name) {
  if (name === 'how-to-play') {
    $('#htp-title').text(t('htpTitle'))
    $('#htp-content').html(t('htpContent'))
    $('#btn-htp-back').text(t('btnBack'))
  } else if (name === 'why-this') {
    $('#why-title').text(t('whyTitle'))
    $('#why-content').html(t('whyContent'))
    $('#btn-why-back').text(t('btnBack'))
  }
}

function initBoard() {
  setTimeout(function() {
    var profile = PROFILES[sessionState.profile || 'standard']
    var maxSize = Math.min(profile.boardSize, window.innerWidth - 32)
    var wrapper = document.getElementById('board-wrapper')
    if (wrapper) wrapper.style.width = maxSize + 'px'
    board = Chessboard('board', {
      position: 'start',
      pieceTheme: 'https://chessboardjs.com/img/chesspieces/wikipedia/{piece}.png',
      showNotation: true,
      width: maxSize
    })
  }, 50)
}

function updateLegendTexts() {
  $('#legend-hanging').text(t('legendHanging'))
  $('#legend-vulnerable').text(t('legendVulnerable'))
}

function squareToSector(square) {
  var file = square.charCodeAt(0) - 97
  if (file <= 2) return 'queenside'
  if (file <= 4) return 'center'
  return 'kingside'
}

function buildExplanation(result) {
  var parts = []
  if (result.missed && result.missed.length) {
    result.missed.forEach(function(m) {
      var typeLabel = m.type === 'hanging'
        ? '<span style="color:#E05C5C">●</span>'
        : '<span style="color:#F6D860">●</span>'
      var text = (m.explanation && m.explanation.trim()) ? m.explanation : (m.square + (m.type ? ' (' + m.type + ')' : ''))
      parts.push(typeLabel + ' ' + text)
    })
  }
  if (result.false_positives && result.false_positives.length) {
    var fpLabel = t('fpExplanation')
    var fpSquares = result.false_positives.map(function(fp) {
      var defStr = fp.defender_piece && fp.defender_square
        ? ' (' + t('defendedBy') + ' ' + fp.defender_piece + ' ' + t('on') + ' ' + fp.defender_square + ')'
        : ''
      return fp.square + defStr
    })
    parts.push(fpLabel + ': ' + fpSquares.join(', '))
  }
  if (!parts.length) parts.push(t('explanationCorrect'))
  return parts.join('<br><br>')
}

function setLang(lang) {
  if (!TRANSLATIONS[lang]) return
  sessionState.lang = lang
  try { window.localStorage.setItem('trainer_lang', lang) } catch (e) {}
  updateLangButtons()
  refreshLanguageForCurrentPhase()
}

function updateLangButtons() {
  $('#lang-toggle .lang-btn').removeClass('active')
  $('#lang-toggle .lang-btn[data-lang="' + sessionState.lang + '"]').addClass('active')
}

function refreshLanguageForCurrentPhase() {
  updateLegendTexts()
  if (sessionState.currentScreen === 'home') {
    renderHomeTexts()
    return
  }
  if (sessionState.currentScreen === 'how-to-play') {
    renderInfoScreen('how-to-play')
    return
  }
  if (sessionState.currentScreen === 'why-this') {
    renderInfoScreen('why-this')
    return
  }
  if (sessionState.currentScreen === 'summary') {
    if (sessionState.summaryData) renderSummaryContent(sessionState.summaryData)
    $('#transfer-q-text').text(t('transferQuestion'))
    var sel = $('#transfer-question .btn-transfer-answer.selected')
    if (sel.length) {
      var val = sel.data('val')
      var msg = (val === '0') ? t('transferResponseZero') : (val === '1') ? t('transferResponseOne') : (val === '2') ? t('transferResponseTwo') : t('transferResponseMore')
      $('#transfer-q-response').text(msg)
    }
    $('#btn-summary-new').text(t('summaryBtnNewRound'))
    $('#btn-summary-home').text(t('summaryBtnHome'))
    return
  }
  if (sessionState.phase === 'loading') {
    $('#instruction').text(t('loading'))
  } else if (sessionState.phase === 'rival_move' && sessionState.currentPuzzle) {
    var p = sessionState.currentPuzzle
    $('#progress').text(t('progressWithLevel')(p.index + 1, sessionState.totalPuzzles, levelLabel(sessionState.level)))
    var pieceDisplay = p.rival_move.piece
    if (sessionState.lang === 'en' && TRANSLATIONS.en.pieceNameEn && TRANSLATIONS.en.pieceNameEn[pieceDisplay]) {
      pieceDisplay = TRANSLATIONS.en.pieceNameEn[pieceDisplay]
    }
    $('#instruction').text(t('rivalMove')(pieceDisplay, p.rival_move.from, p.rival_move.to))
  } else if (sessionState.phase === 'marking') {
    $('#instruction').html(t('markingTitle') + '<br><small>' + t('markingSubtitle') + '</small>')
    var n = sessionState.markedSquares.length
    $('#btn-confirm').text(n === 0 ? t('btnNoDefenders') : t('btnConfirm')(n))
  } else if (sessionState.phase === 'feedback' && sessionState.lastResult) {
    $('#instruction').html(buildExplanation(sessionState.lastResult))
    if (sessionState.lastResult.correct) {
      $('#feedback').html('<span style="color:#7FC97F; font-size:1.2em">' + t('feedbackCorrect') + '</span>')
    } else {
      $('#feedback').html('<span style="color:#E05C5C; font-size:1.2em">' + t('feedbackWrong') + '</span>')
    }
    var scanTimeMs = sessionState.markingStartTime - sessionState.scanStartTime
    var scanSec = (scanTimeMs / 1000).toFixed(1)
    var scanMsg = ''
    var scanColor = '#7FC97F'
    if (scanTimeMs < 3000) { scanMsg = t('scanTimeTooFast')(scanSec); scanColor = '#E8871A' }
    else if (scanTimeMs <= 8000) scanMsg = t('scanTimeGood')(scanSec)
    else scanMsg = t('scanTimeDetailed')(scanSec)
    $('#feedback-scan-time').html('<span style="color:' + scanColor + '; font-size:0.95em">' + scanMsg + '</span>').show()
    var sector = (sessionState.lastResult.missed && sessionState.lastResult.missed[0]) ? squareToSector(sessionState.lastResult.missed[0].square) : 'none'
    var transferText = t('transferDynamic')[sector] || t('transferDynamic').none
    $('#feedback-transfer').html('<div class="summary-transfer" style="margin-top:8px">' + transferText + '</div>').show()
  } else if (sessionState.phase === 'summary' && sessionState.currentScreen === 'training') {
    showSummary()
  }
  if (sessionState.currentScreen === 'training') {
    $('#btn-exit-training').text(t('btnExitTraining'))
  }
}

function startSession() {
  sessionState.streak = 0
  try {
    ['beginner', 'intermediate', 'advanced'].forEach(function(l) {
      window.localStorage.removeItem('trainer_level_suggestion_dismissed_' + l)
    })
  } catch (e) {}
  $('#instruction').text(t('loading'))
  $.get('/api/session/start?level=' + encodeURIComponent(sessionState.selectedLevel), function(data) {
    sessionState.sessionId = data.session_id
    sessionState.totalPuzzles = data.total
    sessionState.level = data.level || sessionState.selectedLevel
    loadPuzzle(data.first_puzzle)
  })
}

function loadPuzzle(data) {
  sessionState.clicksEnabled = false
  sessionState.currentPuzzle = data
  sessionState.markedSquares = []
  sessionState.phase = 'rival_move'

  board.orientation(data.orientation)
  board.position(data.fen, false)

  if (sessionState.timerInterval) {
    clearInterval(sessionState.timerInterval)
    sessionState.timerInterval = null
  }
  $('#decision-timer').text('0.0s')
  $('#timer-container').hide()
  $('#btn-show-timer').hide()

  var pct = (data.total > 0) ? (data.index / data.total) * 100 : 0
  $('#exercise-progress-fill').css('width', pct + '%')
  $('#progress').text(t('progressWithLevel')(data.index + 1, data.total, levelLabel(sessionState.level)))
  $('#feedback').empty().hide()
  $('#feedback-scan-time').empty().hide()
  $('#feedback-transfer').empty().hide()
  $('#legend').hide()
  $('#btn-area').empty()

  var pieceDisplay = data.rival_move.piece
  if (sessionState.lang === 'en' && TRANSLATIONS.en.pieceNameEn && TRANSLATIONS.en.pieceNameEn[pieceDisplay]) {
    pieceDisplay = TRANSLATIONS.en.pieceNameEn[pieceDisplay]
  }
  var rivalMsg = t('rivalMove')(pieceDisplay, data.rival_move.from, data.rival_move.to)
  $('#instruction').text(rivalMsg)

  highlightSquare(data.rival_move.from, '#F6F669')
  highlightSquare(data.rival_move.to, '#F6F669')

  setTimeout(function() {
    clearHighlights()
    startScanPhase()
  }, 2500)
}

function highlightSquare(square, color) {
  var $sq = $('#board .square-' + square)
  $sq.css('background', color)
}

function clearHighlights() {
  $('#board .square-55d63').css('background', '')
  $('#board [class*="square-"]').css('background', '')
  $('.arrow-overlay').remove()
}

function drawArrow(fromSquare, toSquare, color) {
  var boardEl = document.getElementById('board')
  var boardSize = boardEl ? boardEl.offsetWidth : 480
  var squareSize = boardSize / 8
  function squareToCoords(sq, orientation) {
    var file = sq.charCodeAt(0) - 97
    var rank = parseInt(sq[1], 10) - 1
    var col = orientation === 'black' ? 7 - file : file
    var row = orientation === 'black' ? rank : 7 - rank
    return {
      x: col * squareSize + squareSize / 2,
      y: row * squareSize + squareSize / 2
    }
  }
  var orientation = sessionState.currentPuzzle ? sessionState.currentPuzzle.orientation : 'white'
  var from = squareToCoords(fromSquare, orientation)
  var to = squareToCoords(toSquare, orientation)
  var overlay = document.getElementById('scan-overlay')
  if (!overlay) return
  var ns = 'http://www.w3.org/2000/svg'
  var svg = document.createElementNS(ns, 'svg')
  svg.setAttribute('width', boardSize)
  svg.setAttribute('height', boardSize)
  svg.style.position = 'absolute'
  svg.style.top = '0'
  svg.style.left = '0'
  svg.style.pointerEvents = 'none'
  svg.setAttribute('class', 'arrow-overlay')
  var markerId = 'arrowhead-' + fromSquare + '-' + toSquare
  var defs = document.createElementNS(ns, 'defs')
  var marker = document.createElementNS(ns, 'marker')
  marker.setAttribute('id', markerId)
  marker.setAttribute('markerWidth', '4')
  marker.setAttribute('markerHeight', '4')
  marker.setAttribute('refX', '2')
  marker.setAttribute('refY', '2')
  marker.setAttribute('orient', 'auto')
  var polygon = document.createElementNS(ns, 'polygon')
  polygon.setAttribute('points', '0 0, 4 2, 0 4')
  polygon.setAttribute('fill', color)
  marker.appendChild(polygon)
  defs.appendChild(marker)
  svg.appendChild(defs)
  var line = document.createElementNS(ns, 'line')
  line.setAttribute('x1', from.x)
  line.setAttribute('y1', from.y)
  line.setAttribute('x2', to.x)
  line.setAttribute('y2', to.y)
  line.setAttribute('stroke', color)
  line.setAttribute('stroke-width', '3')
  line.setAttribute('stroke-opacity', '0.85')
  line.setAttribute('marker-end', 'url(#' + markerId + ')')
  svg.appendChild(line)
  overlay.appendChild(svg)
}

function startScanPhase() {
  sessionState.phase = 'scanning'
  $('#scan-sector-indicator').hide()

  var sectores = [
    { filesStart: 0, filesCount: 3 },
    { filesStart: 3, filesCount: 2 },
    { filesStart: 5, filesCount: 3 }
  ]

  sessionState.scanStartTime = Date.now()
  var orientation = sessionState.currentPuzzle && sessionState.currentPuzzle.orientation === 'black'

  function clearScanOverlay() {
    document.getElementById('scan-overlay').innerHTML = ''
  }

  function mostrarSector(i) {
    if (i >= sectores.length) {
      clearScanOverlay()
      $('#scan-sector-indicator').hide()
      setTimeout(startMarkingPhase, 300)
      return
    }
    clearScanOverlay()
    var sector = sectores[i]
    $('#instruction').html('<strong style="color:#E8871A">' + t('scanSectors')[i] + '</strong>')
    $('#scan-sector-indicator').text(t('sectorIndicator')(i + 1, 3) + ' — 2s').show()

    var wrapper = document.getElementById('board-wrapper')
    var totalWidth = wrapper ? wrapper.offsetWidth : 560
    var squareWidth = totalWidth / 8
    var x = sector.filesStart * squareWidth
    var w = sector.filesCount * squareWidth
    if (orientation) x = totalWidth - x - w

    var rect = document.createElement('div')
    rect.style.cssText = 'position:absolute; top:0; left:' + x + 'px; width:' + w + 'px; height:100%; background:rgba(168, 216, 234, 0.35);'
    document.getElementById('scan-overlay').appendChild(rect)

    setTimeout(function() {
      clearScanOverlay()
      mostrarSector(i + 1)
    }, 2000)
  }

  mostrarSector(0)
}

function startMarkingPhase() {
  sessionState.phase = 'marking'
  sessionState.markedSquares = []
  sessionState.markingStartTime = Date.now()

  $('#instruction').html(t('markingTitle') + '<br><small>' + t('markingSubtitle') + '</small>')
  $('#legend').show()
  updateLegendTexts()

  $('#btn-area').html(
    '<button id="btn-confirm" class="btn-confirm" disabled>' + t('btnNoDefenders') + '</button>'
  )

  var enableClicks = function() {
    $('#btn-confirm').prop('disabled', false)
    sessionState.clicksEnabled = true
    sessionState.decisionStartTime = Date.now()
    var showTimer = true
    try { showTimer = window.localStorage.getItem('trainer_show_timer') !== 'false' } catch (e) {}
    if (showTimer) { $('#timer-container').show(); $('#btn-show-timer').hide(); $('#btn-toggle-timer').text(t('timerHide')) }
    else { $('#timer-container').hide(); $('#btn-show-timer').text(t('timerShow')).show() }
    $('#decision-timer').text('0.0s').addClass('timer-warning').removeClass('timer-ok')
    sessionState.timerInterval = setInterval(function() {
      if (sessionState.phase !== 'marking') return
      var elapsed = (Date.now() - sessionState.decisionStartTime) / 1000
      $('#decision-timer').text(elapsed.toFixed(1) + 's').toggleClass('timer-warning', elapsed < 3).toggleClass('timer-ok', elapsed >= 3)
    }, 100)
  }
  setTimeout(function() {
    var boardReady = $('#board .square-55d63').length > 0
    if (!boardReady) {
      setTimeout(enableClicks, 200)
    } else {
      enableClicks()
    }
  }, 3000)

  $('#btn-area').on('click', '#btn-confirm', function() {
    submitAnswer()
  })
}

function submitAnswer() {
  $('#btn-confirm').prop('disabled', true)
  if (sessionState.phase !== 'marking') return
  sessionState.phase = 'feedback'
  sessionState.clicksEnabled = false

  if (sessionState.timerInterval) {
    clearInterval(sessionState.timerInterval)
    sessionState.timerInterval = null
  }

  var elapsedMs = Date.now() - sessionState.markingStartTime
  var scanTimeMs = Date.now() - sessionState.decisionStartTime
  sessionState.lastDecisionTimeMs = scanTimeMs

  $('#btn-area').off('click', '#btn-confirm')
  $('#btn-area').empty()

  $.ajax({
    url: '/api/result',
    method: 'POST',
    contentType: 'application/json',
    data: JSON.stringify({
      session_id: sessionState.sessionId,
      puzzle_index: sessionState.currentPuzzle.index,
      marked_squares: sessionState.markedSquares,
      elapsed_ms: elapsedMs,
      scan_time_ms: scanTimeMs,
      lang: sessionState.lang
    }),
    success: function(result) {
      showFeedback(result)
    },
    error: function() {
      if (sessionState.timerInterval) {
        clearInterval(sessionState.timerInterval)
        sessionState.timerInterval = null
      }
    }
  })
}

function playSound(type) {
  if (!sessionState.soundEnabled) return
  try {
    var ctx = new (window.AudioContext || window.webkitAudioContext)()
    var osc = ctx.createOscillator()
    var gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    if (type === 'correct') {
      osc.frequency.setValueAtTime(523, ctx.currentTime)
      osc.frequency.setValueAtTime(659, ctx.currentTime + 0.12)
      gain.gain.setValueAtTime(0.18, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.4)
    } else if (type === 'incorrect') {
      osc.frequency.setValueAtTime(330, ctx.currentTime)
      osc.frequency.setValueAtTime(262, ctx.currentTime + 0.15)
      gain.gain.setValueAtTime(0.12, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.4)
    } else if (type === 'streak') {
      osc.frequency.setValueAtTime(523, ctx.currentTime)
      osc.frequency.setValueAtTime(659, ctx.currentTime + 0.1)
      osc.frequency.setValueAtTime(784, ctx.currentTime + 0.2)
      gain.gain.setValueAtTime(0.18, ctx.currentTime)
      gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.5)
      osc.start(ctx.currentTime)
      osc.stop(ctx.currentTime + 0.5)
    }
  } catch (e) {}
}

function showStreakBadge(n) {
  var existing = document.getElementById('streak-badge')
  if (existing) existing.remove()
  var badge = document.createElement('div')
  badge.id = 'streak-badge'
  badge.style.cssText = [
    'position:fixed',
    'top:4rem',
    'left:50%',
    'transform:translateX(-50%)',
    'background:linear-gradient(135deg, #E8871A, #F6A623)',
    'color:white',
    'padding:8px 20px',
    'border-radius:20px',
    'font-weight:600',
    'font-size:1em',
    'z-index:2000',
    'box-shadow:0 2px 12px rgba(232,135,26,0.4)',
    'animation:streakPop 0.3s ease',
    'pointer-events:none'
  ].join(';')
  var emoji = n >= 10 ? '\uD83D\uDD25\uD83D\uDD25' : n >= 5 ? '\uD83D\uDD25' : '\u26A1'
  badge.textContent = emoji + ' ' + n + ' ' + t('streakLabel')
  document.body.appendChild(badge)
  setTimeout(function() {
    badge.style.transition = 'opacity 0.4s ease'
    badge.style.opacity = '0'
    setTimeout(function() { badge.remove() }, 400)
  }, 1800)
}

function showFeedback(result) {
  sessionState.lastResult = result
  clearHighlights()

  if (result.correct) {
    playSound('correct')
  } else {
    playSound('incorrect')
  }

  var vulnerable = sessionState.currentPuzzle.vulnerable

  Object.keys(vulnerable).forEach(function(square) {
    if (sessionState.markedSquares.includes(square)) {
      highlightSquare(square, '#7FC97F')
    } else {
      var color = vulnerable[square] === 'hanging' ? '#E05C5C' : '#F6D860'
      highlightSquare(square, color)
    }
  })

  sessionState.markedSquares.forEach(function(square) {
    if (!vulnerable[square]) highlightSquare(square, '#E05C5C88')
  })

  if (result.missed && result.missed.length) {
    result.missed.forEach(function(m) {
      if (m.attacker_square) {
        highlightSquare(m.attacker_square, 'rgba(100, 180, 255, 0.7)')
        drawArrow(m.attacker_square, m.square, '#64B4FF')
      }
    })
  }

  $('#legend').hide()

  if (result.correct) {
    sessionState.streak++
    if (sessionState.streak > (sessionState.maxStreak || 0)) {
      sessionState.maxStreak = sessionState.streak
    }
    if (sessionState.streak > 1) {
      showStreakBadge(sessionState.streak)
      if (sessionState.streak % 3 === 0) {
        playSound('streak')
      }
    }
    $('#feedback').removeClass('feedback-wrong').addClass('feedback-correct').html('<span style="color:var(--acento); font-size:1.2em">' + t('feedbackCorrect') + '</span>').show()
  } else {
    sessionState.streak = 0
    $('#feedback').removeClass('feedback-correct').addClass('feedback-wrong').html('<span style="color:var(--error); font-size:1.2em">' + t('feedbackWrong') + '</span>').show()
  }

  $('#instruction').html(buildExplanation(result)).css('margin-top', '12px')

  var scanTimeMs = sessionState.lastDecisionTimeMs != null ? sessionState.lastDecisionTimeMs : 0
  var scanSec = (scanTimeMs / 1000).toFixed(1)
  var scanMsg = ''
  var scanColor = '#7FC97F'
  if (scanTimeMs < 3000) {
    scanMsg = t('scanTimeTooFast')(scanSec)
    scanColor = '#E8871A'
  } else if (scanTimeMs <= 8000) {
    scanMsg = t('scanTimeGood')(scanSec)
  } else {
    scanMsg = t('scanTimeDetailed')(scanSec)
  }
  $('#feedback-scan-time').html('<span style="color:' + scanColor + '; font-size:0.95em">' + scanMsg + '</span>').css('margin-top', '12px').show()

  var sector = (result.missed && result.missed[0]) ? squareToSector(result.missed[0].square) : 'none'
  var transferText = t('transferDynamic')[sector] || t('transferDynamic').none
  $('#feedback-transfer').html('<div class="summary-transfer">' + transferText + '</div>').css('margin-top', '12px').show()

  var btnText = result.correct ? t('btnNext') : t('btnUnderstood')
  $('#btn-area').css('margin-top', '12px').html(
    '<button id="btn-next-puzzle" class="btn-primary btn-menu">' + btnText + '</button>'
  )
  $('#btn-area').on('click', '#btn-next-puzzle', function() {
    nextPuzzle()
  })
}

function nextPuzzle() {
  var nextIndex = sessionState.currentPuzzle.index + 1
  if (nextIndex >= sessionState.totalPuzzles) {
    showSummary()
    return
  }
  $.get('/api/puzzle/' + nextIndex, function(data) {
    loadPuzzle(data)
  })
}

function renderSummaryContent(data) {
  var html = ''
  html += '<div class="summary-stat">'
  html += '<span class="summary-label">' + t('summaryExercises') + '</span>'
  html += '<span class="summary-value">' + data.total + '</span>'
  html += '</div>'
  html += '<div class="summary-stat">'
  html += '<span class="summary-label">' + t('summaryCorrect') + '</span>'
  html += '<span class="summary-value">' + data.correct + '</span>'
  html += '</div>'
  html += '<div class="summary-stat">'
  html += '<span class="summary-label">' + t('summaryAccuracy') + '</span>'
  html += '<span class="summary-value" style="color:' + (data.accuracy >= 70 ? '#4CAF50' : '#E05C5C') + '">' + Math.round(data.accuracy) + '%</span>'
  html += '</div>'
  var avgSec = (data.avg_time_ms / 1000).toFixed(1)
  html += '<div class="summary-stat">'
  html += '<span class="summary-label">' + t('summaryAvgTime') + '</span>'
  html += '<span class="summary-value">' + avgSec + 's</span>'
  html += '</div>'
  if (sessionState.maxStreak >= 3) {
    html += '<div class="summary-insight" style="color:#E8871A">'
    html += '\u26A1 ' + t('summaryMaxStreak') + ': ' + sessionState.maxStreak
    html += '</div>'
  }
  if (data.sector_weakness) {
    var sectorLabel = (t('sectorNames')[data.sector_weakness] != null ? t('sectorNames')[data.sector_weakness] : data.sector_weakness)
    html += '<div class="summary-insight" style="color:#E8871A">'
    html += t('summarySectorWeak') + ' <strong>' + sectorLabel + '</strong>'
    html += '<br><small>' + t('summarySectorHint') + '</small>'
    html += '</div>'
  }
  var scanSec = (data.avg_scan_time_ms / 1000).toFixed(1)
  html += '<div class="summary-insight">'
  html += t('summaryScanTime') + ' <strong>' + scanSec + 's</strong>'
  html += '</div>'
  if (data.false_positive_rate > 0.3) {
    html += '<div class="summary-insight" style="color:#E05C5C">'
    html += t('summaryFpWarningTitle')
    html += '<br><small>' + t('summaryFpWarningHint') + '</small>'
    html += '</div>'
  }
  html += '<div class="summary-transfer">'
  html += t('summaryTransfer')
  html += '</div>'
  $('#summary-content').html(html)
  $('#transfer-q-text').text(t('transferQuestion'))
  $('#transfer-q-response').hide().empty()
  $('#transfer-question .btn-transfer-answer').removeClass('selected')
  $('#transfer-question').show()
}

function showSummary() {
  sessionState.phase = 'summary'
  clearHighlights()
  board.position('start')
  showScreen('summary')
  $('#summary-content').text(t('loadingResults'))
  $('#btn-summary-new').text(t('summaryBtnNewRound'))
  $('#btn-summary-home').text(t('summaryBtnHome'))

  $.get('/api/session/summary/' + sessionState.sessionId, function(data) {
    sessionState.summaryData = data
    renderSummaryContent(data)
    bindTransferAnswerButtons()
    var history = getHistoryByLevel()
    var level = sessionState.level || sessionState.selectedLevel
    if (!history[level]) history[level] = []
    history[level].push({
      date: new Date().toLocaleDateString(),
      correct: data.correct,
      total: data.total,
      accuracy: Math.round(data.accuracy),
      avgTime: data.avg_time_ms != null ? (data.avg_time_ms / 1000) : null,
      piecesLost: null
    })
    if (history[level].length > 10) history[level] = history[level].slice(-10)
    try {
      window.localStorage.setItem('trainer_history', JSON.stringify(history))
    } catch (e) {}
  })
}

function bindTransferAnswerButtons() {
  $(document).off('click', '.btn-transfer-answer').on('click', '.btn-transfer-answer', function() {
    var val = $(this).data('val')
    $('#transfer-question .btn-transfer-answer').removeClass('selected')
    $(this).addClass('selected')
    try { window.localStorage.setItem('trainer_last_pieces_lost', val) } catch (e) {}
    var msg = ''
    if (val === '0') msg = t('transferResponseZero')
    else if (val === '1') msg = t('transferResponseOne')
    else if (val === '2') msg = t('transferResponseTwo')
    else msg = t('transferResponseMore')
    $('#transfer-q-response').text(msg).show()
    var history = getHistoryByLevel()
    var level = sessionState.level || sessionState.selectedLevel
    var arr = history[level] || []
    if (arr.length) {
      arr[arr.length - 1].piecesLost = val
      history[level] = arr
      try { window.localStorage.setItem('trainer_history', JSON.stringify(history)) } catch (e2) {}
    }
  })
}

function toggleSound() {
  sessionState.soundEnabled = !sessionState.soundEnabled
  try { window.localStorage.setItem('trainer_sound', sessionState.soundEnabled) } catch (e) {}
  $('#btn-sound-toggle').text(sessionState.soundEnabled ? '\uD83D\uDD0A' : '\uD83D\uDD07')
}

$(document).ready(function() {
  try {
    var savedLang = window.localStorage.getItem('trainer_lang')
    if (savedLang && TRANSLATIONS[savedLang]) sessionState.lang = savedLang
    sessionState.soundEnabled = window.localStorage.getItem('trainer_sound') !== 'false'
  } catch (e) {}
  updateLegendTexts()
  updateLangButtons()
  $('#btn-sound-toggle').text(sessionState.soundEnabled ? '\uD83D\uDD0A' : '\uD83D\uDD07')
  $('#btn-sound-toggle').on('click', function() { toggleSound() })

  $(document).on('click', '#lang-toggle .lang-btn', function() {
    var lang = $(this).data('lang')
    setLang(lang)
  })
  $(document).on('click', '#board .square-55d63', function() {
    if (!sessionState.clicksEnabled) return
    if (sessionState.phase !== 'marking') return
    var squareClass = $(this).attr('class').match(/square-([a-h][1-8])/)
    if (!squareClass) return
    var square = squareClass[1]
    if (sessionState.markedSquares.includes(square)) {
      sessionState.markedSquares = sessionState.markedSquares.filter(function(s) { return s !== square })
      $(this).css('background', '')
    } else {
      sessionState.markedSquares.push(square)
      $(this).css('background', '#F6F66988')
    }
    var n = sessionState.markedSquares.length
    $('#btn-confirm').text(n === 0 ? t('btnNoDefenders') : t('btnConfirm')(n))
  })

  $('#btn-new-round').on('click', function() {
    showScreen('training')
    if (!board) initBoard()
    startSession()
  })
  $('#btn-how-to-play').on('click', function() {
    renderInfoScreen('how-to-play')
    showScreen('how-to-play')
  })
  $('#btn-why-this').on('click', function() {
    renderInfoScreen('why-this')
    showScreen('why-this')
  })
  $('#btn-htp-back, #btn-why-back').on('click', function() {
    showScreen('home')
  })
  $('#btn-exit-training').on('click', function() {
    if (confirm(t('exitConfirm'))) {
      if (sessionState.timerInterval) {
        clearInterval(sessionState.timerInterval)
        sessionState.timerInterval = null
      }
      $('#timer-container').hide()
      $('#btn-show-timer').hide()
      $('#decision-timer').text('0.0s')
      showScreen('home')
      renderHomeTexts()
    }
  })
  $(document).on('click', '#btn-toggle-timer', function() {
    try { window.localStorage.setItem('trainer_show_timer', 'false') } catch (e) {}
    $('#timer-container').hide()
    $('#btn-show-timer').text(t('timerShow')).show()
    $('#btn-toggle-timer').text(t('timerHide'))
  })
  $(document).on('click', '#btn-show-timer', function() {
    try { window.localStorage.setItem('trainer_show_timer', 'true') } catch (e) {}
    $('#timer-container').show()
    $('#btn-show-timer').hide()
    $('#btn-toggle-timer').text(t('timerHide'))
  })
  $('#btn-summary-new').on('click', function() {
    showScreen('training')
    if (!board) initBoard()
    startSession()
  })
  $('#btn-summary-home').on('click', function() {
    showScreen('home')
    renderHomeTexts()
  })

  var profileKey = 'standard'
  try { profileKey = window.localStorage.getItem('trainer_profile') || 'standard' } catch (e) {}
  if (!PROFILES[profileKey]) profileKey = 'standard'
  applyProfile(profileKey)

  $(document).on('click', '#profile-selector .profile-btn, #profile-overlay .profile-btn', function() {
    var key = $(this).data('profile')
    if (key) {
      applyProfile(key)
      $('#profile-overlay').removeClass('profile-overlay-visible')
    }
  })
  $('#btn-profile-gear').on('click', function() {
    $('#profile-overlay').addClass('profile-overlay-visible')
  })
  $('#profile-overlay').on('click', function(e) {
    if (e.target === this || $(e.target).hasClass('profile-overlay-backdrop')) $('#profile-overlay').removeClass('profile-overlay-visible')
  })

  showScreen('home')
  renderHomeTexts()
  $('#btn-exit-training').text(t('btnExitTraining'))

  $(window).on('resize orientationchange', function() {
    if (sessionState.profile) applyProfile(sessionState.profile)
    else if (board) board.resize()
  })
})
