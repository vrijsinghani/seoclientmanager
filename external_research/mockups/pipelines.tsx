"use client"

import { useState } from "react"
import { Plus, Search, MoreHorizontal, Play, Pause, StopCircle, Pencil, Trash2 } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog"
import { Label } from "@/components/ui/label"
import { Textarea } from "@/components/ui/textarea"

type PipelineStage = {
  id: number
  name: string
  crew: string
  tasks: string[]
}

type Pipeline = {
  id: number
  name: string
  description: string
  status: "Idle" | "Running" | "Paused" | "Completed" | "Failed"
  stages: PipelineStage[]
}

export default function PipelineDashboard() {
  const [pipelines, setPipelines] = useState<Pipeline[]>([
    {
      id: 1,
      name: "Customer Feedback Analysis",
      description: "Analyze and respond to customer feedback",
      status: "Running",
      stages: [
        { id: 1, name: "Data Collection", crew: "Data Analysis Crew", tasks: ["Collect feedback", "Preprocess data"] },
        { id: 2, name: "Sentiment Analysis", crew: "ML Crew", tasks: ["Run sentiment model", "Categorize feedback"] },
        { id: 3, name: "Response Generation", crew: "Content Creation Crew", tasks: ["Draft responses", "Review responses"] },
        { id: 4, name: "Customer Communication", crew: "Customer Support Crew", tasks: ["Send responses", "Track engagement"] },
      ]
    },
    {
      id: 2,
      name: "Product Development Pipeline",
      description: "End-to-end product development process",
      status: "Idle",
      stages: [
        { id: 1, name: "Ideation", crew: "Research Crew", tasks: ["Market research", "Concept development"] },
        { id: 2, name: "Design", crew: "Design Crew", tasks: ["Create mockups", "User testing"] },
        { id: 3, name: "Development", crew: "Engineering Crew", tasks: ["Implement features", "Quality assurance"] },
        { id: 4, name: "Launch", crew: "Marketing Crew", tasks: ["Prepare marketing materials", "Coordinate launch"] },
      ]
    },
  ])

  const [searchTerm, setSearchTerm] = useState("")
  const [showPipelineDialog, setShowPipelineDialog] = useState(false)
  const [currentPipeline, setCurrentPipeline] = useState<Pipeline | null>(null)

  const filteredPipelines = pipelines.filter(pipeline => 
    pipeline.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    pipeline.description.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleDeletePipeline = (pipelineId: number) => {
    setPipelines(pipelines.filter(pipeline => pipeline.id !== pipelineId))
  }

  const handleSavePipeline = (pipeline: Pipeline) => {
    if (pipeline.id) {
      setPipelines(pipelines.map(p => p.id === pipeline.id ? pipeline : p))
    } else {
      setPipelines([...pipelines, { ...pipeline, id: pipelines.length + 1 }])
    }
    setShowPipelineDialog(false)
  }

  const handleStatusChange = (pipelineId: number, newStatus: Pipeline['status']) => {
    setPipelines(pipelines.map(p => p.id === pipelineId ? { ...p, status: newStatus } : p))
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Pipeline Dashboard</h1>
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <Input
          placeholder="Search pipelines..."
          className="w-full md:w-64"
          type="search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <Button onClick={() => { setCurrentPipeline(null); setShowPipelineDialog(true) }}>
          <Plus className="mr-2 h-4 w-4" />
          Create Pipeline
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {filteredPipelines.map((pipeline) => (
          <Card key={pipeline.id}>
            <CardHeader>
              <CardTitle className="flex justify-between items-center">
                <span>{pipeline.name}</span>
                <Badge variant={
                  pipeline.status === "Running" ? "default" :
                  pipeline.status === "Paused" ? "secondary" :
                  pipeline.status === "Completed" ? "success" :
                  pipeline.status === "Failed" ? "destructive" :
                  "outline"
                }>{pipeline.status}</Badge>
              </CardTitle>
              <CardDescription>{pipeline.description}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-2">
                {pipeline.stages.map((stage, index) => (
                  <div key={stage.id} className="flex items-center">
                    <div className="w-6 h-6 rounded-full bg-primary text-primary-foreground flex items-center justify-center text-sm font-bold">
                      {index + 1}
                    </div>
                    <div className="ml-2 flex-grow">
                      <p className="text-sm font-medium">{stage.name}</p>
                      <p className="text-xs text-muted-foreground">{stage.crew}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
            <CardFooter className="flex justify-between">
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline">Actions</Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent>
                  <DropdownMenuItem onClick={() => handleStatusChange(pipeline.id, "Running")}>
                    <Play className="mr-2 h-4 w-4" />
                    Start
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleStatusChange(pipeline.id, "Paused")}>
                    <Pause className="mr-2 h-4 w-4" />
                    Pause
                  </DropdownMenuItem>
                  <DropdownMenuItem onClick={() => handleStatusChange(pipeline.id, "Idle")}>
                    <StopCircle className="mr-2 h-4 w-4" />
                    Stop
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={() => { setCurrentPipeline(pipeline); setShowPipelineDialog(true) }}>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem className="text-red-600" onClick={() => handleDeletePipeline(pipeline.id)}>
                    <Trash2 className="mr-2 h-4 w-4" />
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
              <Button variant="secondary">View Details</Button>
            </CardFooter>
          </Card>
        ))}
      </div>

      <Dialog open={showPipelineDialog} onOpenChange={setShowPipelineDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{currentPipeline ? 'Edit Pipeline' : 'Create New Pipeline'}</DialogTitle>
            <DialogDescription>
              {currentPipeline ? 'Edit the details of your pipeline below.' : 'Enter the details of your new pipeline below.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => {
            e.preventDefault()
            const formData = new FormData(e.currentTarget)
            const newPipeline: Pipeline = {
              id: currentPipeline?.id || 0,
              name: formData.get('name') as string,
              description: formData.get('description') as string,
              status: "Idle",
              stages: currentPipeline?.stages || [],
            }
            handleSavePipeline(newPipeline)
          }}>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  Name
                </Label>
                <Input id="name" name="name" defaultValue={currentPipeline?.name} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="description" className="text-right">
                  Description
                </Label>
                <Textarea id="description" name="description" defaultValue={currentPipeline?.description} className="col-span-3" />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit">Save Pipeline</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}