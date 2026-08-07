import {
  Line,
  LineChart as RechartsLineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  CartesianGrid,
} from 'recharts'

interface LineChartProps<T> {
  data: T[]
  xKey: keyof T
  yKey: keyof T
}

const LineChart = <T extends object>({
  data,
  xKey,
  yKey,
}: LineChartProps<T>) => {
  return (
    <ResponsiveContainer
      width="100%"
      height={320}
    >
      <RechartsLineChart data={data}>
        <CartesianGrid strokeDasharray="3 3" />

        <XAxis dataKey={String(xKey)} />

        <YAxis />

        <Tooltip />

        <Line
          type="monotone"
          dataKey={String(yKey)}
          stroke="#2563eb"
          strokeWidth={3}
          dot={{ r: 5 }}
          activeDot={{ r: 7 }}
        />
      </RechartsLineChart>
    </ResponsiveContainer>
  )
}

export default LineChart