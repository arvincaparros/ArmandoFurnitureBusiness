import {
  Cell,
  Pie,
  PieChart as RechartsPieChart,
  ResponsiveContainer,
  Tooltip,
} from 'recharts'

interface PieChartProps<T> {
  data: T[]
  nameKey: keyof T
  valueKey: keyof T
}

const COLORS = [
  '#2563eb',
  '#16a34a',
  '#ea580c',
  '#0891b2',
  '#9333ea',
]

const PieChart = <T extends object>({
  data,
  nameKey,
  valueKey,
}: PieChartProps<T>) => {
  return (
    <ResponsiveContainer
      width="100%"
      height={320}
    >
      <RechartsPieChart>
        <Pie
          data={data}
          dataKey={String(valueKey)}
          nameKey={String(nameKey)}
          innerRadius={70}
          outerRadius={110}
          paddingAngle={3}
        >
          {data.map((_, index) => (
            <Cell
              key={index}
              fill={COLORS[index % COLORS.length]}
            />
          ))}
        </Pie>

        <Tooltip />
      </RechartsPieChart>
    </ResponsiveContainer>
  )
}

export default PieChart