export default function Table({ head, rows }: { head: string[]; rows: React.ReactNode[][] }) {
  return (
    <div className="neu-raised overflow-x-auto p-2">
      <table className="w-full text-sm border-collapse">
        <thead>
          <tr>
            {head.map(h => (
              <th
                key={h}
                scope="col"
                className="text-left px-4 py-3 font-semibold"
                style={{ color: 'var(--cp-muted)' }}
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i}>
              {r.map((c, j) => (
                <td key={j} className="px-4 py-3">
                  {c}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
