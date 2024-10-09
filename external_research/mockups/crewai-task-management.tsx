"use client"

import { useState } from "react"
import { Plus, Search, Filter, MoreHorizontal, Pencil, Trash2, Save, ArrowUpDown } from "lucide-react"

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
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar"
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
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Textarea } from "@/components/ui/textarea"
import { Label } from "@/components/ui/label"

type Task = {
  id: number
  description: string
  assignedAgent: string
  expectedOutput: string
  tools: string[]
  context: string
  sequence: number
  dependencies: number[]
}

export default function CrewAITaskManagement() {
  const [tasks, setTasks] = useState<Task[]>([
    { id: 1, description: "Analyze customer feedback data", assignedAgent: "Data Analyst", expectedOutput: "Comprehensive report on customer satisfaction trends", tools: ["Python", "Pandas", "Matplotlib"], context: "Q2 Sales Data", sequence: 1, dependencies: [] },
    { id: 2, description: "Generate response templates based on common inquiries", assignedAgent: "Content Writer", expectedOutput: "Set of 10 response templates for frequently asked questions", tools: ["GPT-3", "Grammarly"], context: "Customer Support Guidelines", sequence: 2, dependencies: [1] },
    { id: 3, description: "Implement automated response system", assignedAgent: "ML Engineer", expectedOutput: "Functional chatbot integrated with support platform", tools: ["TensorFlow", "DialogFlow", "Python"], context: "Customer Support Platform", sequence: 3, dependencies: [2] },
  ])

  const [searchTerm, setSearchTerm] = useState("")
  const [showTaskDialog, setShowTaskDialog] = useState(false)
  const [currentTask, setCurrentTask] = useState<Task | null>(null)

  const filteredTasks = tasks.filter(task => 
    task.description.toLowerCase().includes(searchTerm.toLowerCase()) ||
    task.assignedAgent.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const handleDeleteTask = (taskId: number) => {
    setTasks(tasks.filter(task => task.id !== taskId))
  }

  const handleSaveTask = (task: Task) => {
    if (task.id) {
      setTasks(tasks.map(t => t.id === task.id ? task : t))
    } else {
      setTasks([...tasks, { ...task, id: tasks.length + 1, sequence: tasks.length + 1 }])
    }
    setShowTaskDialog(false)
  }

  const handleSaveAsTemplate = (task: Task) => {
    // In a real application, this would save the task as a template
    console.log("Saving task as template:", task)
  }

  const handleMoveTask = (taskId: number, direction: 'up' | 'down') => {
    const taskIndex = tasks.findIndex(t => t.id === taskId)
    if ((direction === 'up' && taskIndex > 0) || (direction === 'down' && taskIndex < tasks.length - 1)) {
      const newTasks = [...tasks]
      const swapIndex = direction === 'up' ? taskIndex - 1 : taskIndex + 1
      [newTasks[taskIndex], newTasks[swapIndex]] = [newTasks[swapIndex], newTasks[taskIndex]]
      newTasks.forEach((task, index) => task.sequence = index + 1)
      setTasks(newTasks)
    }
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">CrewAI Task Management</h1>
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <Input
          placeholder="Search tasks..."
          className="w-full md:w-64"
          type="search"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <Button onClick={() => { setCurrentTask(null); setShowTaskDialog(true) }}>
          <Plus className="mr-2 h-4 w-4" />
          Create Task
        </Button>
      </div>

      <div className="space-y-4">
        {filteredTasks.map((task) => (
          <Card key={task.id}>
            <CardHeader>
              <CardTitle className="text-lg flex justify-between items-center">
                <span>Task {task.sequence}: {task.description}</span>
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <Button variant="ghost" size="sm">
                      <MoreHorizontal className="h-4 w-4" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end">
                    <DropdownMenuItem onClick={() => { setCurrentTask(task); setShowTaskDialog(true) }}>
                      <Pencil className="mr-2 h-4 w-4" />
                      Edit
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleSaveAsTemplate(task)}>
                      <Save className="mr-2 h-4 w-4" />
                      Save as Template
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => handleMoveTask(task.id, 'up')}>
                      <ArrowUpDown className="mr-2 h-4 w-4" />
                      Move Up
                    </DropdownMenuItem>
                    <DropdownMenuItem onClick={() => handleMoveTask(task.id, 'down')}>
                      <ArrowUpDown className="mr-2 h-4 w-4" />
                      Move Down
                    </DropdownMenuItem>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem className="text-red-600" onClick={() => handleDeleteTask(task.id)}>
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <p className="font-semibold">Assigned Agent:</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Avatar className="h-6 w-6">
                      <AvatarImage src={`https://api.dicebear.com/6.x/initials/svg?seed=${task.assignedAgent}`} alt={task.assignedAgent} />
                      <AvatarFallback>{task.assignedAgent.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                    </Avatar>
                    <span>{task.assignedAgent}</span>
                  </div>
                </div>
                <div>
                  <p className="font-semibold">Expected Output:</p>
                  <p className="mt-1">{task.expectedOutput}</p>
                </div>
                <div>
                  <p className="font-semibold">Tools:</p>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {task.tools.map((tool, index) => (
                      <Badge key={index} variant="secondary">{tool}</Badge>
                    ))}
                  </div>
                </div>
                <div>
                  <p className="font-semibold">Context:</p>
                  <p className="mt-1">{task.context}</p>
                </div>
              </div>
              {task.dependencies.length > 0 && (
                <div className="mt-4">
                  <p className="font-semibold">Dependencies:</p>
                  <div className="flex flex-wrap gap-2 mt-1">
                    {task.dependencies.map((depId) => (
                      <Badge key={depId} variant="outline">Task {depId}</Badge>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      <Dialog open={showTaskDialog} onOpenChange={setShowTaskDialog}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>{currentTask ? 'Edit Task' : 'Create New Task'}</DialogTitle>
            <DialogDescription>
              {currentTask ? 'Edit the details of your task below.' : 'Enter the details of your new task below.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={(e) => {
            e.preventDefault()
            const formData = new FormData(e.currentTarget)
            const newTask: Task = {
              id: currentTask?.id || 0,
              description: formData.get('description') as string,
              assignedAgent: formData.get('assignedAgent') as string,
              expectedOutput: formData.get('expectedOutput') as string,
              tools: (formData.get('tools') as string).split(',').map(tool => tool.trim()),
              context: formData.get('context') as string,
              sequence: currentTask?.sequence || tasks.length + 1,
              dependencies: (formData.get('dependencies') as string).split(',').map(dep => parseInt(dep.trim())).filter(dep => !isNaN(dep)),
            }
            handleSaveTask(newTask)
          }}>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="description" className="text-right">
                  Description
                </Label>
                <Textarea id="description" name="description" defaultValue={currentTask?.description} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="assignedAgent" className="text-right">
                  Assigned Agent
                </Label>
                <Input id="assignedAgent" name="assignedAgent" defaultValue={currentTask?.assignedAgent} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="expectedOutput" className="text-right">
                  Expected Output
                </Label>
                <Textarea id="expectedOutput" name="expectedOutput" defaultValue={currentTask?.expectedOutput} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="tools" className="text-right">
                  Tools
                </Label>
                <Input id="tools" name="tools" defaultValue={currentTask?.tools.join(', ')} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="context" className="text-right">
                  Context
                </Label>
                <Input id="context" name="context" defaultValue={currentTask?.context} className="col-span-3" />
              </div>
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="dependencies" className="text-right">
                  Dependencies
                </Label>
                <Input id="dependencies" name="dependencies" defaultValue={currentTask?.dependencies.join(', ')} className="col-span-3" />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit">Save Tasks</Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
