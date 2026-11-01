/** First column is the row header. Numeric columns are right-aligned and tabular. */
export function DataTable({ caption, columns, rows, rowKey, isSelected }) {
  return (
    <div className="table-wrap" role="region" aria-label={caption} tabIndex={0}>
      <table className="table">
        <caption className="sr-only">{caption}</caption>
        <thead>
          <tr>
            {columns.map((c) => (
              <th key={c.key} scope="col" className={c.numeric ? 'is-num' : undefined}>{c.header}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={rowKey(row)} data-selected={isSelected?.(row) || undefined}>
              {columns.map((c, i) =>
                i === 0 ? (
                  <th key={c.key} scope="row">{c.render(row)}</th>
                ) : (
                  <td key={c.key} className={c.numeric ? 'is-num num' : undefined}>{c.render(row)}</td>
                ),
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
