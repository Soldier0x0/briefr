import DataGrid from '../../../components/ui/DataGrid.jsx'

/** ARCH workspace DataGrid — shared primitive with section-scoped styling. */
export default function ArchDataGrid(props) {
  const { className = '', ...rest } = props
  return (
    <DataGrid
      {...rest}
      className={['sa-arch-grid', className].filter(Boolean).join(' ')}
      tableClassName="admin-table sa-arch-grid-table data-grid-table"
    />
  )
}
