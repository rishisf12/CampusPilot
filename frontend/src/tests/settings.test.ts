/**
 * Tests for the Settings registry and the timetable row helpers.
 *
 * The registry is the file every future setting is added to, and its mistakes are
 * silent: a bad default renders a switch in the wrong position, a `mirror` on a
 * local setting is dead config, and nothing anywhere throws. So most of what
 * follows checks the registry's *invariants* rather than behaviour - the kind of
 * thing that is cheap to assert and expensive to notice by eye.
 *
 * `coerceSetting` is here for one specific reason: storage and the server
 * document are both editable outside the app, and a boolean arriving as the
 * string "false" is truthy. Trusting a cast there inverts a switch.
 *
 * Run with:  cd frontend && npm test
 */
import assert from 'node:assert/strict';
import { describe, test } from 'vitest';

import {
  SETTINGS_DEFAULTS,
  SETTINGS_REGISTRY,
  SETTINGS_SECTIONS,
  coerceSetting,
  settingsForSection,
  type SettingsEntry,
} from '@shared/constants';
import {
  FREE_PERIOD_MINUTES,
  formatDuration,
  rowsForDay,
  subjectHue,
  subjectTint,
} from '@shared/features/schedule/timetableRows';
import { daysUntilWeekday, weekOrderStartingOn } from '@shared/lib/time';
import type { TimetableSlot } from '@shared/types/api';

// ------------------------------------------------------------------ registry

describe('Settings registry invariants', () => {
  test('every setting key is unique', () => {
    const keys = SETTINGS_REGISTRY.map(entry => entry.key);
    const duplicates = keys.filter((key, i) => keys.indexOf(key) !== i);
    assert.deepEqual(duplicates, [], `duplicate setting keys: ${duplicates.join(', ')}`);
  });

  test('every setting names a section that exists', () => {
    const sections = new Set(SETTINGS_SECTIONS.map(section => section.id));
    for (const entry of SETTINGS_REGISTRY) {
      assert.ok(sections.has(entry.section), `${entry.key} names unknown section ${entry.section}`);
    }
  });

  test('every section is reachable from the tab list', () => {
    const withEntries = new Set(SETTINGS_REGISTRY.map(entry => entry.section));
    const listed = new Set(SETTINGS_SECTIONS.map(section => section.id));
    for (const id of withEntries) {
      assert.ok(listed.has(id), `section ${id} has settings but no tab`);
    }
  });

  test('a choice setting has choices, and its default is one of them', () => {
    for (const entry of SETTINGS_REGISTRY.filter(e => e.type === 'choice')) {
      assert.ok(entry.choices?.length, `${entry.key} is a choice but lists no options`);
      const values = entry.choices!.map(choice => choice.value);
      assert.ok(
        values.includes(String(entry.default)),
        `${entry.key} defaults to "${entry.default}", which is not one of ${values.join(', ')}`
      );
    }
  });

  test('choice values are unique within a setting', () => {
    for (const entry of SETTINGS_REGISTRY.filter(e => e.type === 'choice')) {
      const values = entry.choices!.map(choice => choice.value);
      assert.equal(new Set(values).size, values.length, `${entry.key} repeats a choice value`);
    }
  });

  test('only a server-backed setting may mirror a device copy', () => {
    // A local setting is already on the device; mirroring it would write the same
    // key twice and make the source of truth ambiguous.
    for (const entry of SETTINGS_REGISTRY.filter(e => e.mirror)) {
      assert.equal(entry.store, 'server', `${entry.key} mirrors but is stored locally`);
    }
  });

  test('a mirrored setting is readable before the first paint', () => {
    // The point of a mirror is boot-time correctness, so it must be a setting the
    // app applies immediately (theme) rather than one read later.
    const mirrored = SETTINGS_REGISTRY.filter(e => e.mirror).map(e => e.key);
    assert.ok(mirrored.length > 0, 'expected at least one mirrored setting');
    assert.ok(mirrored.includes('theme'), 'theme must be mirrored or a reload flashes');
  });

  test('every setting carries a label and help text', () => {
    for (const entry of SETTINGS_REGISTRY) {
      assert.ok(entry.label?.trim(), `${entry.key} has no label`);
      assert.ok(entry.help?.trim(), `${entry.key} has no help text`);
    }
  });

  test('defaults table agrees with the registry', () => {
    for (const entry of SETTINGS_REGISTRY) {
      assert.deepEqual(
        SETTINGS_DEFAULTS[entry.key],
        entry.default,
        `${entry.key} default disagrees with the registry`
      );
    }
  });

  test('settingsForSection returns the section, in order', () => {
    for (const section of SETTINGS_SECTIONS) {
      const entries = settingsForSection(section.id);
      for (const entry of entries) {
        assert.equal(entry.section, section.id);
      }
      const orders = entries.map(e => e.order ?? 0);
      assert.deepEqual(
        orders,
        [...orders].sort((a, b) => a - b),
        `${section.id} is out of order`
      );
    }
  });
});

// ----------------------------------------------------------------- coercion

describe('coerceSetting', () => {
  const bool: SettingsEntry = {
    key: 'b',
    section: 'privacy',
    label: 'B',
    help: '',
    type: 'boolean',
    default: false,
    store: 'server',
  };
  const choice: SettingsEntry = {
    key: 'c',
    section: 'schedule',
    label: 'C',
    help: '',
    type: 'choice',
    default: 'Mon',
    choices: [
      { value: 'Mon', label: 'Monday' },
      { value: 'Sat', label: 'Saturday' },
    ],
    store: 'server',
  };
  const num: SettingsEntry = {
    key: 'n',
    section: 'schedule',
    label: 'N',
    help: '',
    type: 'number',
    default: 75,
    store: 'server',
  };

  test('the string "false" is false, not truthy', () => {
    // The whole reason coerceSetting exists: a cast would return true here and
    // silently invert the switch.
    assert.equal(coerceSetting(bool, 'false'), false);
    assert.equal(coerceSetting(bool, 'true'), true);
  });

  test('a real boolean passes through', () => {
    assert.equal(coerceSetting(bool, true), true);
    assert.equal(coerceSetting(bool, false), false);
  });

  test('nonsense falls back to the default', () => {
    assert.equal(coerceSetting(bool, 'banana'), false);
    assert.equal(coerceSetting(choice, 'Tue'), 'Mon');
    assert.equal(coerceSetting(num, 'not a number'), 75);
  });

  test('numbers arrive as strings from storage', () => {
    assert.equal(coerceSetting(num, '60'), 60);
    assert.equal(coerceSetting(num, 60), 60);
  });

  test('a missing value is the default', () => {
    assert.equal(coerceSetting(choice, undefined), 'Mon');
    assert.equal(coerceSetting(num, null), 75);
  });

  test('every registry entry coerces its own default to itself', () => {
    for (const entry of SETTINGS_REGISTRY) {
      assert.deepEqual(
        coerceSetting(entry, entry.default),
        entry.default,
        `${entry.key} does not survive its own default`
      );
    }
  });
});

// ------------------------------------------------------------- week ordering

describe('weekOrderStartingOn', () => {
  test('Monday is the default order', () => {
    assert.deepEqual(weekOrderStartingOn('Mon'), ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
  });

  test('a Saturday week starts on Saturday', () => {
    assert.deepEqual(weekOrderStartingOn('Sat'), ['Sat', 'Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri']);
  });

  test('a Sunday week starts on Sunday', () => {
    assert.deepEqual(weekOrderStartingOn('Sun'), ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat']);
  });

  test('an unknown start falls back to Monday rather than emptying the week', () => {
    // A bad stored value must not blank the timetable.
    assert.deepEqual(weekOrderStartingOn('nonsense'), weekOrderStartingOn('Mon'));
    assert.deepEqual(weekOrderStartingOn(undefined), weekOrderStartingOn('Mon'));
    assert.deepEqual(weekOrderStartingOn(''), weekOrderStartingOn('Mon'));
  });

  test('every ordering is all seven days exactly once', () => {
    for (const start of ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun', 'bogus']) {
      const order = weekOrderStartingOn(start);
      assert.equal(order.length, 7, `${start} produced ${order.length} days`);
      assert.equal(new Set(order).size, 7, `${start} repeated or dropped a day`);
      assert.equal(order[0], start === 'bogus' ? 'Mon' : start);
    }
  });

  test('daysUntilWeekday wraps forward', () => {
    // Today is pinned to a Friday. These assertions only hold on a Friday, so
    // the day is passed in rather than read from the clock: this test used to
    // fail on four days out of seven and pass on three, which is the kind of
    // flake that gets dismissed as unrelated.
    const friday = new Date('2026-10-16T09:00:00'); // a Friday, local time

    assert.equal(daysUntilWeekday('Fri', friday), 0);
    assert.equal(daysUntilWeekday('Sat', friday), 1);
    assert.equal(daysUntilWeekday('Sun', friday), 2);
    assert.equal(daysUntilWeekday('Mon', friday), 3);
  });

  test('an unknown target is treated as today', () => {
    assert.equal(daysUntilWeekday('nonsense', new Date('2026-10-16T09:00:00')), 0);
  });
});

// ------------------------------------------------------------- timetable rows

function slot(id: number, start: string, end: string): TimetableSlot {
  return {
    id,
    day: 'Mon',
    start_time: start,
    end_time: end,
    room: 'L-101',
    course_code: `CS${1000 + id}`,
    branch_or_program: 'CSE',
    semester: 1,
  };
}

describe('rowsForDay', () => {
  test('back-to-back classes produce no free rows', () => {
    const rows = rowsForDay([slot(1, '09:00', '09:55'), slot(2, '09:55', '10:50')], true);
    assert.equal(rows.length, 2);
    assert.ok(rows.every(row => row.kind === 'slot'));
  });

  test('a long gap becomes a free row', () => {
    const rows = rowsForDay([slot(1, '09:00', '09:55'), slot(2, '11:00', '11:55')], true);
    assert.equal(rows.length, 3);
    const free = rows[1];
    assert.equal(free.kind, 'free');
    if (free.kind === 'free') {
      assert.equal(free.from, '09:55');
      assert.equal(free.to, '11:00');
      assert.equal(free.minutes, 65);
    }
  });

  test('a short gap is not worth naming', () => {
    const short = slot(2, '10:00', '10:55');
    const rows = rowsForDay([slot(1, '09:00', '09:55'), short], true);
    assert.equal(rows.length, 2, 'a 5 minute gap should not become a free period');
  });

  test('the threshold is inclusive', () => {
    // 09:55 -> 10:40 is exactly 45 minutes.
    const rows = rowsForDay([slot(1, '09:00', '09:55'), slot(2, '10:40', '11:35')], true);
    assert.ok(rows.some(row => row.kind === 'free'));
    assert.equal(FREE_PERIOD_MINUTES, 45);
  });

  test('free rows are suppressed entirely when the setting is off', () => {
    const rows = rowsForDay([slot(1, '09:00', '09:55'), slot(2, '14:00', '14:55')], false);
    assert.equal(rows.length, 2);
    assert.ok(rows.every(row => row.kind === 'slot'));
  });

  test('the gap before the first class is never marked', () => {
    // 07:00 to 09:00 is two hours, but it is the morning, not a free period.
    const rows = rowsForDay([slot(1, '09:00', '09:55'), slot(2, '14:00', '14:55')], true);
    assert.equal(rows.filter(row => row.kind === 'free').length, 1);
    assert.equal(rows[0].kind, 'slot', 'the first row must be a class');
  });

  test('the last class never gets a trailing free row', () => {
    const rows = rowsForDay([slot(1, '09:00', '09:55')], true);
    assert.equal(rows.length, 1);
  });

  test('an empty day produces nothing', () => {
    assert.deepEqual(rowsForDay([], true), []);
  });

  test('the caller slot type survives', () => {
    type Rich = TimetableSlot & { sort_key: number };
    const rich: Rich = { ...slot(1, '09:00', '09:55'), sort_key: 540 };
    const rows = rowsForDay([rich], true);
    assert.equal(rows[0].kind, 'slot');
    if (rows[0].kind === 'slot') assert.equal(rows[0].slot.sort_key, 540);
  });
});

describe('formatDuration', () => {
  test('minutes under an hour read as minutes', () => {
    assert.equal(formatDuration(5), '5 min');
    assert.equal(formatDuration(45), '45 min');
  });

  test('whole hours drop the minutes', () => {
    assert.equal(formatDuration(60), '1 hr');
    assert.equal(formatDuration(120), '2 hr');
  });

  test('mixed reads as hours and minutes', () => {
    assert.equal(formatDuration(95), '1 hr 35 min');
  });
});

describe('subjectTint', () => {
  test('the same course always gets the same colour', () => {
    // A timetable that recolours itself between renders is unreadable.
    assert.deepEqual(subjectTint('CS3001'), subjectTint('CS3001'));
  });

  test('different courses generally differ', () => {
    assert.notEqual(subjectHue('CS3001'), subjectHue('ME2002'));
  });

  test('an empty code still produces a usable colour', () => {
    // A slot whose code failed to parse must not render as an invalid hue.
    assert.ok(Number.isFinite(subjectHue('')));
    // Space-separated hsl(), which is the modern form the tint emits.
    assert.match(subjectTint('').edge, /^hsl\(\d+ 65% 45%\)$/);
  });

  test('the hue stays in range', () => {
    for (const code of ['CS3001', 'ME2002', '', 'ZZZZ', 'OE3M27']) {
      const hue = subjectHue(code);
      assert.ok(hue >= 0 && hue < 360, `${code} produced hue ${hue}`);
    }
  });
});
