import { notifications } from '@mantine/notifications'
import {
  ArchiveRestore,
  CheckCircle2,
  Pencil,
  Trash2,
  Save,
  Download,
} from 'lucide-react'

export const notify = {
  added(name: string) {
    notifications.show({
      color: 'green',
      title: 'Resource Added',
      message: `${name} was added successfully.`,
      icon: <CheckCircle2 size={18} />,
    })
  },

  updated(name: string) {
    notifications.show({
      color: 'blue',
      title: 'Resource Updated',
      message: `${name} was updated successfully.`,
      icon: <Pencil size={18} />,
    })
  },

  // `name` is accepted for a consistent call signature with the
  // other notify.* helpers even though the message text doesn't
  // currently interpolate it - keeping the parameter means a future
  // per-resource-name variant of this message won't require every
  // call site to change. The `void name` below is only to satisfy
  // noUnusedParameters/no-unused-vars without renaming the parameter.
  resourceNeedsReoptimization(name: string) {
    void name

    notifications.show({
      color: 'orange',
      title: 'Resource Updated — Re-optimization Required',
      message:
        'The resource quantity has been updated successfully. Your existing production allocation may no longer be feasible or optimal based on the updated resources. Please generate a new Optimal Production Plan and apply it to update your production allocation.',
      icon: <Pencil size={18} />,
      autoClose: false,
    })
  },

  deleted(name: string) {
    notifications.show({
      color: 'red',
      title: 'Resource Deleted',
      message: `${name} was deleted successfully.`,
      icon: <Trash2 size={18} />,
    })
  },

  // Distinct from deleted() above, which reports the reversible
  // soft delete - this one reports a row that is gone for good and
  // says so, so the two outcomes are never confused in the UI.
  permanentlyDeleted(name: string) {
    notifications.show({
      color: 'red',
      title: 'Resource Permanently Deleted',
      message: `${name} was removed from the resource catalog. This cannot be undone.`,
      icon: <Trash2 size={18} />,
    })
  },

  reactivated(name: string) {
    notifications.show({
      color: 'green',
      title: 'Resource Reactivated',
      message: `${name} is now active again.`,
      icon: <ArchiveRestore size={18} />,
    })
  },

  saved() {
    notifications.show({
      color: 'teal',
      title: 'Changes Saved',
      message: 'All changes were saved successfully.',
      icon: <Save size={18} />,
    })
  },

  exported(type: 'CSV' | 'Excel') {
    notifications.show({
      color: 'green',
      title: `${type} Export Complete`,
      message: `Your ${type} file was downloaded successfully.`,
      icon: <Download size={18} />,
    })
  },

  applied() {
    notifications.show({
      color: 'green',
      title: 'Plan Applied',
      message:
        'The optimal plan has been committed as the production allocation for this cycle.',
      icon: <CheckCircle2 size={18} />,
    })
  },

  generated() {
    notifications.show({
      color: 'green',
      title: 'Optimization Generated',
      message:
        'A new optimization run was generated and added to the history.',
      icon: <CheckCircle2 size={18} />,
    })
  },
}