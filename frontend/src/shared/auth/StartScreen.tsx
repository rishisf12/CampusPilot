import { useCallback, useEffect, useState } from 'react';
import { GraduationCap, ShieldCheck, ArrowRight } from 'lucide-react';
import { Badge, Button } from '@/components/ui';

import AnimatedLogo from './AnimatedLogo';
import AnimatedTitle from './AnimatedTitle';
import TechBackground from './TechBackground';

/**
 * The landing screen: who are you signing in as?
 *
 * Student is the full app; admin is the developer sign-in for feedback
 * responses. Faculty gets its own signup: department instead of the student
 * cohort fields, and a teaching-schedule workspace after sign-in.
 *
 * The cards carry a single short line each. An earlier version had a second
 * "detail" sentence on every card ("Track your classes, attendance, exam
 * seating and vacant rooms. Sign in with your password, a passkey, or your
 * college email.") plus a "Choose your role to continue." subtitle and a
 * "Students register with your college email address." footer. Three sentences
 * saying what a label already says, before the user had chosen anything.
 *
 * Two choices were made here on purpose:
 *
 * - **Nothing is stored.** The choice is not persisted, so no new localStorage
 *   key is introduced for what is only a routing decision. Picking a role again
 *   costs one click.
 * - **No role is claimed by picking.** The account's own role decides what
 *   opens; picking admin with a student account signs straight back out.
 */
interface Role {
  id: string;
  label: string;
  /** One short line. The card shows nothing else. */
  description: string;
  available: boolean;
  /** Accent tint for the card. See the .cp-choice--* rules in index.css. */
  hue: 'teal' | 'amber' | 'violet';
}

const ROLES: Role[] = [
  {
    id: 'student',
    label: 'Student',
    description: 'Timetable, attendance, exams, rooms.',
    available: true,
    hue: 'teal',
  },
  {
    id: 'faculty',
    label: 'Faculty',
    description: 'Teaching schedule.',
    available: true,
    hue: 'amber',
  },
  {
    id: 'admin',
    label: 'Admin',
    description: 'Feedback responses.',
    available: true,
    hue: 'violet',
  },
];

/** The first line the intro types out, one letter at a time. */
const WELCOME = 'Welcome to the';

/** One pass of the landing intro, in ms from the top. It runs once - no loop.
 *  The values are 40% of the original intro: same beats, same order, 60% less
 *  wait before the sign-in card is on screen. */
const INTRO = {
  /** Hand pops in and starts waving. */
  hand: 760,
  /** "Hi" pops. */
  hi: 1360,
  /** "Hi" fades away. */
  hiOut: 1860,
  /** "Welcome to the" starts typing. */
  typeStart: 2000,
  /** Gap between letters while typing. */
  typeStep: 30,
  /** The wordmark appears. */
  wordmark: 2640,
  /** The sign-in card rises in - this marks completion. */
  card: 2960,
} as const;

/** How long the hand keeps waving after the intro has finished, before it is
 *  let go. Long enough to read as a farewell, short enough not to hover over
 *  the wordmark and card for the rest of the session. */
const HAND_LINGER_MS = 5000;

/** The hand's fade-out, in ms. It must match `.cp-logo-hand--out` in
 *  index.css - the element stays mounted this long, then unmounts. */
const HAND_EXIT_MS = 180;

/** True when the visitor has asked for less motion, in which case the intro
 *  shows its end state once and never loops. */
function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () =>
      typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches
  );

  useEffect(() => {
    const query = window.matchMedia('(prefers-reduced-motion: reduce)');
    const update = () => setReduced(query.matches);
    query.addEventListener('change', update);
    return () => query.removeEventListener('change', update);
  }, []);

  return reduced;
}

interface LandingLockupProps {
  /** When true the intro shows its end state once and never loops. */
  reduced: boolean;
  /** Called as the wordmark lands, to bring the sign-in card in after it. */
  onReveal: () => void;
}

/**
 * The landing lockup, played as a single intro:
 *
 *   1. the face settles (the logo's own draw-in)
 *   2. the hand pops in and waves
 *   3. "Hi" pops, then fades
 *   4. "Welcome to the" is typed out
 *   5. the wordmark appears
 *   6. the card rises in - this marks completion, and "Welcome to the"
 *      disappears so the wordmark and card have the stage to themselves
 *   7. HAND_LINGER_MS later the hand waves goodbye (fades, stage 7), then
 *      unmounts (stage 8) - it does not hover over the settled lockup
 *
 * It runs once and never restarts. `onReveal` fires when the card rises in,
 * and the card then stays put.
 *
 * Deliberately local to this screen - no other page asks for it, and the logo
 * only shows the hand while this runs.
 */
function LandingLockup({ reduced, onReveal }: LandingLockupProps) {
  const [stage, setStage] = useState(0);
  const [typed, setTyped] = useState(0);

  useEffect(() => {
    if (reduced) return;

    const timers: number[] = [];
    const at = (ms: number, run: () => void) => timers.push(window.setTimeout(run, ms));

    at(INTRO.hand, () => setStage(1));
    at(INTRO.hi, () => setStage(2));
    at(INTRO.hiOut, () => setStage(3));
    at(INTRO.typeStart, () => setStage(4));
    for (let i = 1; i <= WELCOME.length; i += 1) {
      at(INTRO.typeStart + i * INTRO.typeStep, () => setTyped(i));
    }
    at(INTRO.wordmark, () => setStage(5));
    at(INTRO.card, () => {
      onReveal();
      // Completion: the card has risen in, so "Welcome to the" steps aside.
      setStage(6);
      // The hand has done its job; it waves through the linger window, fades,
      // and is then removed from the tree for good.
      at(INTRO.card + HAND_LINGER_MS, () => setStage(7));
      at(INTRO.card + HAND_LINGER_MS + HAND_EXIT_MS, () => setStage(8));
    });

    return () => timers.forEach(clearTimeout);
  }, [reduced, onReveal]);

  const showHand = !reduced && stage >= 1 && stage < 8;
  const handOut = !reduced && stage === 7;
  const showHi = !reduced && (stage === 2 || stage === 3);
  // "Welcome to the" shows while typing and alongside the wordmark, then
  // disappears once the card rises in (stage 6 = intro complete).
  const typing = !reduced && stage >= 4 && stage < 6;
  const showWordmark = reduced || stage >= 5;

  return (
    <div className="cp-lockup text-center mb-8">
      <AnimatedLogo size={72} hand={showHand} handOut={handOut} />
      <div className="mt-3">
        <div className="cp-intro-slot">
          {showHi && <span className={`cp-hi${stage === 3 ? ' cp-hi--out' : ''}`}>Hi</span>}
          {typing && (
            <p className="cp-welcome">
              {WELCOME.slice(0, typed)}
              {typed < WELCOME.length && <span className="cp-caret" />}
            </p>
          )}
        </div>
        <div className="cp-wordmark-slot">{showWordmark && <AnimatedTitle />}</div>
      </div>
    </div>
  );
}

interface StartScreenProps {
  onChooseStudent?: () => void;
  onChooseFaculty?: () => void;
  onChooseAdmin?: () => void;
  /** Sign in with an existing account, rather than creating one. */
  onSignIn?: () => void;
}

export default function StartScreen({
  onChooseStudent,
  onChooseFaculty,
  onChooseAdmin,
  onSignIn,
}: StartScreenProps) {
  const reduced = usePrefersReducedMotion();
  // The card is held back until the intro is ready for it, then stays. It is
  // deliberately not tied to the loop, so it does not blink out on a restart.
  const [cardVisible, setCardVisible] = useState(reduced);
  const revealCard = useCallback(() => setCardVisible(true), []);

  useEffect(() => {
    if (reduced) setCardVisible(true);
  }, [reduced]);

  const pick = (id: string) => {
    if (id === 'admin') onChooseAdmin?.();
    else if (id === 'faculty') onChooseFaculty?.();
    else onChooseStudent?.();
  };
  return (
    <div className="cp-auth-root min-h-screen flex items-center justify-center px-4 py-12">
      <TechBackground />

      <div className="relative w-full max-w-2xl">
        <LandingLockup reduced={reduced} onReveal={revealCard} />

        <div className={`cp-card space-y-5${cardVisible ? '' : ' cp-card--waiting'}`}>
          <h2 className="text-lg font-semibold text-center" style={{ color: 'var(--cp-text)' }}>
            Create a new account
          </h2>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ROLES.map(role => (
              <RoleCard key={role.id} role={role} onChoose={() => pick(role.id)} />
            ))}
          </div>

          <p className="text-xs text-center" style={{ color: 'var(--cp-muted)' }}>
            Already have an account?
          </p>
          <Button
            type="button"
            variant="ghost"
            size="sm"
            className="w-full"
            onClick={onSignIn}
            aria-label="Sign in to an existing account"
          >
            Sign in
          </Button>
        </div>
      </div>
    </div>
  );
}

function RoleCard({ role, onChoose }: { role: Role; onChoose: () => void }) {
  const Icon = role.id === 'admin' ? ShieldCheck : GraduationCap;
  if (!role.available) {
    return (
      <div
        className={`cp-choice-static cp-choice--${role.hue}`}
        // Not a control: there is nothing to click, so it is not a button.
        aria-disabled="true"
      >
        <div className="flex items-center justify-between gap-2">
          <span
            className="font-semibold flex items-center gap-1.5"
            style={{ color: 'var(--cp-muted)' }}
          >
            <Icon size={18} aria-hidden className="cp-choice-icon" /> {role.label}
          </span>
          <Badge tone="neutral">Soon</Badge>
        </div>
        <p className="text-xs mt-1.5" style={{ color: 'var(--cp-muted)' }}>
          {role.description}
        </p>
      </div>
    );
  }

  return (
    <button
      type="button"
      onClick={onChoose}
      aria-label={`Continue as ${role.label}`}
      className={`cp-choice cp-choice--${role.hue}`}
    >
      <div className="flex items-center justify-between gap-2">
        <span
          className="font-semibold flex items-center gap-1.5"
          style={{ color: 'var(--cp-text)' }}
        >
          <Icon size={18} aria-hidden className="cp-choice-icon" /> {role.label}
        </span>
        <span aria-hidden="true" className="cp-choice-arrow">
          <ArrowRight size={18} />
        </span>
      </div>
      <p className="text-xs mt-1.5" style={{ color: 'var(--cp-muted)' }}>
        {role.description}
      </p>
    </button>
  );
}
