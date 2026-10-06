/**
 * The landing screen: who are you signing in as?
 *
 * Student is the full app; admin is the developer sign-in for feedback
 * responses. Faculty is shown so the shape of the product is visible, but it
 * says plainly that it is not built yet rather than offering a form that
 * would fail.
 *
 * Two choices were made here on purpose:
 *
 * - **Nothing is stored.** The choice is not persisted, so no new localStorage
 *   key is introduced for what is only a routing decision. Picking a role again
 *   costs one click.
 * - **No role is claimed by picking.** The account's own role decides what
 *   opens; picking admin with a student account signs straight back out.
 */
const ROLES = [
  {
    id: 'student',
    label: 'Student',
    description: 'Your timetable, attendance, exam hall and seats.',
    available: true,
    detail:
      'Track your classes, attendance, exam seating and vacant rooms. Sign in with your password, a passkey, or your college email.',
  },
  {
    id: 'faculty',
    label: 'Faculty',
    description: 'Teaching schedule and your classes.',
    available: false,
    detail: 'Not built yet. Faculty accounts are on the way.',
  },
  {
    id: 'admin',
    label: 'Admin',
    description: 'Feedback responses and publishing.',
    available: true,
    detail: 'Developer sign-in to answer student feedback.',
  },
]

export default function StartScreen({ onChooseStudent, onChooseAdmin }) {
  const pick = (id) => {
    if (id === 'admin') onChooseAdmin?.()
    else onChooseStudent?.()
  }
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center px-4 py-12">
      <div className="w-full max-w-2xl">
        <div className="text-center mb-8">
          <img src="/logo-icon.svg" alt="Essential" className="w-16 h-16 mx-auto" />
          <h1 className="mt-3 text-2xl font-bold text-primary-500">essential</h1>
          <p className="text-xs tracking-widest text-primary-400 font-medium">
            YOUR CAMPUS ASSISTANT
          </p>
        </div>

        <div className="card space-y-5">
          <div className="text-center">
            <h2 className="text-lg font-semibold text-gray-900">How are you signing in?</h2>
            <p className="text-sm text-gray-600 mt-1">Choose your role to continue.</p>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
            {ROLES.map((role) => (
              <RoleCard key={role.id} role={role} onChoose={() => pick(role.id)} />
            ))}
          </div>

          <p className="text-xs text-gray-500 text-center pt-1">
            Students register with your college email address.
          </p>
        </div>
      </div>
    </div>
  )
}

function RoleCard({ role, onChoose }) {
  if (!role.available) {
    return (
      <div
        className="rounded-xl border border-gray-200 bg-gray-50 p-4 text-left"
        // Not a control: there is nothing to click, so it is not a button.
        aria-disabled="true"
      >
        <div className="flex items-center justify-between gap-2">
          <span className="font-semibold text-gray-500">{role.label}</span>
          <span className="text-[10px] font-medium uppercase tracking-wide px-1.5 py-0.5 rounded bg-gray-200 text-gray-500">
            Soon
          </span>
        </div>
        <p className="text-xs text-gray-500 mt-1.5">{role.detail}</p>
      </div>
    )
  }

  return (
    <button
      type="button"
      onClick={onChoose}
      className="rounded-xl border-2 border-primary-500 bg-primary-50 p-4 text-left hover:bg-primary-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 transition-colors"
    >
      <div className="flex items-center justify-between gap-2">
        <span className="font-semibold text-primary-700">{role.label}</span>
        <span aria-hidden="true" className="text-primary-500">
          &rarr;
        </span>
      </div>
      <p className="text-xs text-primary-600 mt-1.5">{role.detail}</p>
    </button>
  )
}
