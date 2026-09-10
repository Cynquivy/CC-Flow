import { useMemo } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  Handle,
  Position,
  MarkerType,
  type Node,
  type Edge,
  type NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import dagre from '@dagrejs/dagre'
import type { CatalogCourse, CourseStatus } from './types'

const NODE_WIDTH = 190
const NODE_HEIGHT = 56

const STATUS_LABEL: Record<CourseStatus, string> = {
  completed: 'Completed',
  'eligible-now': 'Eligible now',
  locked: 'Locked',
  'needs-retake': 'Needs retake',
}

interface CourseNodeData extends Record<string, unknown> {
  code: string
  name: string
  units: number
  status: CourseStatus
}

type CourseNodeType = Node<CourseNodeData, 'course'>

function CourseNode({ data }: NodeProps<CourseNodeType>) {
  return (
    <div className={`course-node course-node--${data.status}`} title={STATUS_LABEL[data.status]}>
      <Handle type="target" position={Position.Top} />
      <div className="course-node__code">{data.code}</div>
      <div className="course-node__name">{data.name || '(untitled)'}</div>
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

const nodeTypes = { course: CourseNode }

const ISOLATED_GRID_COLUMNS = 8
const ISOLATED_GRID_GAP_Y = 100

function toNode(
  code: string,
  x: number,
  y: number,
  courseByCode: Map<string, CatalogCourse>,
  statuses: Record<string, CourseStatus>,
): CourseNodeType {
  const course = courseByCode.get(code)!
  return {
    id: code,
    type: 'course',
    position: { x, y },
    data: {
      code: course.code,
      name: course.name,
      units: course.units,
      status: statuses[code] ?? 'locked',
    },
  }
}

function layout(courses: CatalogCourse[], statuses: Record<string, CourseStatus>) {
  const courseByCode = new Map(courses.map((c) => [c.code, c]))
  const knownCodes = new Set(courses.map((c) => c.code))

  const edges: Edge[] = []
  const connectedCodes = new Set<string>()
  for (const course of courses) {
    for (const req of course.requisites) {
      if (req.type !== 'hard' && req.type !== 'coreq') continue
      if (!knownCodes.has(req.code)) continue
      edges.push({
        id: `${req.code}->${course.code}-${req.type}`,
        source: req.code,
        target: course.code,
        type: 'smoothstep',
        style: req.type === 'coreq' ? { strokeDasharray: '5,4' } : undefined,
        markerEnd: { type: MarkerType.ArrowClosed },
      })
      connectedCodes.add(req.code)
      connectedCodes.add(course.code)
    }
  }

  // dagre lays out each weakly-connected component side by side -- with as
  // many single-course "components" as this dataset has (electives, PE,
  // NSTP, etc. with no prereqs and nothing depending on them), that balloons
  // the layout to thousands of pixels wide for no reason. Lay out only the
  // courses that actually participate in a prereq/coreq edge via dagre, then
  // grid-pack everything else (genuinely isolated -- no relationships to
  // show) densely underneath instead of giving each its own column.
  const g = new dagre.graphlib.Graph()
  g.setGraph({ rankdir: 'TB', nodesep: 28, ranksep: 64 })
  g.setDefaultEdgeLabel(() => ({}))
  for (const code of connectedCodes) {
    g.setNode(code, { width: NODE_WIDTH, height: NODE_HEIGHT })
  }
  for (const edge of edges) {
    g.setEdge(edge.source, edge.target)
  }
  dagre.layout(g)

  const nodes: CourseNodeType[] = []
  let maxY = 0
  for (const code of connectedCodes) {
    const pos = g.node(code)
    maxY = Math.max(maxY, pos.y)
    nodes.push(toNode(code, pos.x - NODE_WIDTH / 2, pos.y - NODE_HEIGHT / 2, courseByCode, statuses))
  }

  const isolatedGridTop = connectedCodes.size > 0 ? maxY + ISOLATED_GRID_GAP_Y : 0
  const isolated = courses.filter((c) => !connectedCodes.has(c.code))
  isolated.forEach((course, i) => {
    const col = i % ISOLATED_GRID_COLUMNS
    const row = Math.floor(i / ISOLATED_GRID_COLUMNS)
    nodes.push(
      toNode(
        course.code,
        col * (NODE_WIDTH + 20),
        isolatedGridTop + row * (NODE_HEIGHT + 20),
        courseByCode,
        statuses,
      ),
    )
  })

  return { nodes, edges }
}

interface CourseGraphProps {
  courses: CatalogCourse[]
  statuses: Record<string, CourseStatus>
}

export function CourseGraph({ courses, statuses }: CourseGraphProps) {
  const { nodes, edges } = useMemo(() => layout(courses, statuses), [courses, statuses])

  return (
    <div className="course-graph">
      <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} nodesDraggable={false} fitView>
        <Background />
        <Controls showInteractive={false} />
        <MiniMap pannable zoomable />
      </ReactFlow>
    </div>
  )
}
