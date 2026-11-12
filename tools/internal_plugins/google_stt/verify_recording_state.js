// Pure decision-table test for the two-signal recording state: no browser,
// no network. Covers every combination of (waveform class, toggle label)
// including the two disagreement directions and the "both buttons gone"
// case, because those are exactly the paths that must never be guessed.
const { classifyRecordingState } = require('./playwright_runner.js');

const CASES = [
  // wave, stop-button count, mic-button count, expected
  [true, 1, 0, 'recording', 'both say recording'],
  [false, 0, 1, 'auto_stopped', 'both say idle (platform ended capture)'],
  [false, 1, 0, 'signal_disagreement', 'waveform gone but toggle still says recording'],
  [true, 0, 1, 'signal_disagreement', 'waveform present but toggle says idle'],
  [false, 0, 0, 'signal_disagreement', 'no waveform and no toggle at all (page changed?)'],
  [true, 0, 0, 'signal_disagreement', 'waveform present, toggle not found'],
  [true, 1, 1, 'recording', 'both toggle labels visible: stop wins'],
];

let failed = 0;
for (const [wave, stopCount, micCount, expected, why] of CASES) {
  const got = classifyRecordingState(wave, stopCount, micCount);
  const ok = got === expected;
  if (!ok) failed++;
  console.log(`${ok ? 'PASS' : 'FAIL'}  wave=${wave} stop=${stopCount} mic=${micCount} -> ${got}${ok ? '' : ` (expected ${expected})`}  # ${why}`);
}
console.log(`\n${CASES.length - failed}/${CASES.length} checks passed`);
process.exitCode = failed ? 1 : 0;