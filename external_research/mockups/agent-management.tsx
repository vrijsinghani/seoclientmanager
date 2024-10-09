"use client"

import { useState } from "react"
import { Plus, Search, Filter, MoreHorizontal, Pencil, Trash2, UserPlus } from "lucide-react"
import { format } from "date-fns"

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

export default function AgentManagement() {
  const [agents, setAgents] = useState([
    { id: 1, name: "Data Analyst", role: "Analyst", skills: ["Python", "SQL", "Data Visualization"], status: "Active", crew: "Data Analysis Crew" },
    { id: 2, name: "Customer Support Rep", role: "Support", skills: ["Communication", "Problem Solving"], status: "Idle", crew: "Customer Support Crew" },
    { id: 3, name: "Content Writer", role: "Creator", skills: ["Copywriting", "SEO", "Research"], status: "Active", crew: "Content Creation Crew" },
    { id: 4, name: "ML Engineer", role: "Engineer", skills: ["Machine Learning", "TensorFlow", "PyTorch"], status: "Active", crew: "Data Analysis Crew" },
    { id: 5, name: "Social Media Manager", role: "Manager", skills: ["Social Media Marketing", "Content Planning"], status: "Idle", crew: "Content Creation Crew" },
  ])

  const [filterRole, setFilterRole] = useState("")
  const [filterStatus, setFilterStatus] = useState("")
  const [searchTerm, setSearchTerm] = useState("")

  const filteredAgents = agents.filter(agent => 
    (filterRole === "" || agent.role === filterRole) &&
    (filterStatus === "" || agent.status === filterStatus) &&
    (searchTerm === "" || agent.name.toLowerCase().includes(searchTerm.toLowerCase()) || agent.skills.some(skill => skill.toLowerCase().includes(searchTerm.toLowerCase())))
  )

  const handleDeleteAgent = (agentId: number) => {
    setAgents(agents.filter(agent => agent.id !== agentId))
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Agent Management</h1>
      
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-6 gap-4">
        <div className="flex flex-col sm:flex-row gap-4 w-full md:w-auto">
          <Input
            placeholder="Search agents..."
            className="w-full sm:w-64"
            type="search"
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
          <Select value={filterRole} onValueChange={setFilterRole}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue placeholder="Filter by role" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Roles</SelectItem>
              <SelectItem value="Analyst">Analyst</SelectItem>
              <SelectItem value="Support">Support</SelectItem>
              <SelectItem value="Creator">Creator</SelectItem>
              <SelectItem value="Engineer">Engineer</SelectItem>
              <SelectItem value="Manager">Manager</SelectItem>
            </SelectContent>
          </Select>
          <Select value={filterStatus} onValueChange={setFilterStatus}>
            <SelectTrigger className="w-full sm:w-40">
              <SelectValue placeholder="Filter by status" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Statuses</SelectItem>
              <SelectItem value="Active">Active</SelectItem>
              <SelectItem value="Idle">Idle</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <Button className="w-full md:w-auto">
          <UserPlus className="mr-2 h-4 w-4" />
          Create Agent
        </Button>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        {filteredAgents.map((agent) => (
          <Card key={agent.id}>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{agent.name}</span>
                <Avatar className="h-10 w-10">
                  <AvatarImage src={`https://api.dicebear.com/6.x/initials/svg?seed=${agent.name}`} alt={agent.name} />
                  <AvatarFallback>{agent.name.split(' ').map(n => n[0]).join('')}</AvatarFallback>
                </Avatar>
              </CardTitle>
              <CardDescription>{agent.role}</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="mb-4">
                <span className="font-semibold">Skills:</span>
                <div className="flex flex-wrap gap-2 mt-2">
                  {agent.skills.map((skill, index) => (
                    <Badge key={index} variant="secondary">{skill}</Badge>
                  ))}
                </div>
              </div>
              <div className="mb-4">
                <span className="font-semibold">Status:</span>{" "}
                <Badge variant={agent.status === "Active" ? "default" : "secondary"}>{agent.status}</Badge>
              </div>
              <div>
                <span className="font-semibold">Crew:</span> {agent.crew}
              </div>
            </CardContent>
            <CardFooter className="justify-between">
              <Button variant="outline">View Details</Button>
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="ghost" className="h-8 w-8 p-0">
                    <MoreHorizontal className="h-4 w-4" />
                    <span className="sr-only">Open menu</span>
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuLabel>Actions</DropdownMenuLabel>
                  <DropdownMenuItem>
                    <Pencil className="mr-2 h-4 w-4" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuSeparator />
                  <Dialog>
                    <DialogTrigger asChild>
                      <DropdownMenuItem onSelect={(e) => e.preventDefault()} className="text-red-600">
                        <Trash2 className="mr-2 h-4 w-4" />
                        Delete
                      </DropdownMenuItem>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Are you sure you want to delete this agent?</DialogTitle>
                        <DialogDescription>
                          This action cannot be undone. This will permanently delete the agent
                          and remove its data from our servers.
                        </DialogDescription>
                      </DialogHeader>
                      <DialogFooter>
                        <Button variant="outline">Cancel</Button>
                        <Button variant="destructive" onClick={() => handleDeleteAgent(agent.id)}>Delete</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </DropdownMenuContent>
              </DropdownMenu>
            </CardFooter>
          </Card>
        ))}
      </div>
    </div>
  )
}