import DataGrid from '../../../components/ui/DataGrid.jsx'

/**
 * Admin-styled DataGrid — thin wrapper over the shared ui/DataGrid primitive.
 */
export default function AdminDataGrid(props) {
  return (
    <DataGrid
      key={props.gridId}
      {...props}
      className={['admin-data-grid', props.className].filter(Boolean).join(' ')}
      tableClassName="admin-table admin-data-grid-table data-grid-table"
    />
  )
}
