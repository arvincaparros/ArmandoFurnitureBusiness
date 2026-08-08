import { notifications } from '@mantine/notifications'
import {
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

  deleted(name: string) {
    notifications.show({
      color: 'red',
      title: 'Resource Deleted',
      message: `${name} was deleted successfully.`,
      icon: <Trash2 size={18} />,
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
}