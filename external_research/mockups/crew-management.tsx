"use client"

import { useState } from "react"
import { Plus, Search, Filter, MoreHorizontal, Pencil, Trash2 } from "lucide-react"
import { format } from "date-fns"

import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table"
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
import { Checkbox } from "@/components/ui/checkbox"

export default function CrewManagement() {
  const [crews, setCrews] = useState([
    { id: 1, name: "Data Analysis Crew", status: "Active", created: new Date(2023, 5, 15), lastModified: new Date(2023, 11, 10) },
    { id: 2, name: "Customer Support Crew", status: "Idle", created: new Date(2023, 7, 22), lastModified: new Date(2023, 10, 5) },
    { id: 3, name: "Content Creation Crew", status: "In Progress", created: new Date(2023, 9, 1), lastModified: new Date(2023, 11, 20) },
  ])

  const [selectedCrews, setSelectedCrews] = useState<number[]>([])

  const handleSelectCrew = (crewId: number) => {
    setSelectedCrews(prev => 
      prev.includes(crewId) ? prev.filter(id => id !== crewId) : [...prev, crewId]
    )
  }

  const handleSelectAll = () => {
    setSelectedCrews(selectedCrews.length === crews.length ? [] : crews.map(crew => crew.id))
  }

  const handleDeleteCrew = (crewId: number) => {
    setCrews(crews.filter(crew => crew.id !== crewId))
    setSelectedCrews(selectedCrews.filter(id => id !== crewId))
  }

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-3xl font-bold mb-6">Crew Management</h1>
      
      <div className="flex justify-between items-center mb-6">
        <div className="flex gap-4">
          <Input
            placeholder="Search crews..."
            className="w-64"
            type="search"
            icon={<Search className="h-4 w-4 opacity-50" />}
          />
          <Button variant="outline">
            <Filter className="mr-2 h-4 w-4" />
            Filter
          </Button>
        </div>
        <div className="flex gap-4">
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Create Crew
          </Button>
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="outline" disabled={selectedCrews.length === 0}>Bulk Actions</Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent>
              <DropdownMenuItem>Export Selected</DropdownMenuItem>
              <DropdownMenuItem className="text-red-600">Delete Selected</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="border rounded-lg">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-12">
                <Checkbox
                  checked={selectedCrews.length === crews.length}
                  onCheckedChange={handleSelectAll}
                  aria-label="Select all crews"
                />
              </TableHead>
              <TableHead>Name</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created Date</TableHead>
              <TableHead>Last Modified</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {crews.map((crew) => (
              <TableRow key={crew.id}>
                <TableCell>
                  <Checkbox
                    checked={selectedCrews.includes(crew.id)}
                    onCheckedChange={() => handleSelectCrew(crew.id)}
                    aria-label={`Select ${crew.name}`}
                  />
                </TableCell>
                <TableCell className="font-medium">{crew.name}</TableCell>
                <TableCell>
                  <span className={`inline-block px-2 py-1 text-xs font-semibold rounded-full ${
                    crew.status === "Active" ? "bg-green-100 text-green-800" :
                    crew.status === "Idle" ? "bg-yellow-100 text-yellow-800" :
                    "bg-blue-100 text-blue-800"
                  }`}>
                    {crew.status}
                  </span>
                </TableCell>
                <TableCell>{format(crew.created, 'MMM d, yyyy')}</TableCell>
                <TableCell>{format(crew.lastModified, 'MMM d, yyyy')}</TableCell>
                <TableCell className="text-right">
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
                            <DialogTitle>Are you sure you want to delete this crew?</DialogTitle>
                            <DialogDescription>
                              This action cannot be undone. This will permanently delete the crew
                              and remove its data from our servers.
                            </DialogDescription>
                          </DialogHeader>
                          <DialogFooter>
                            <Button variant="outline">Cancel</Button>
                            <Button variant="destructive" onClick={() => handleDeleteCrew(crew.id)}>Delete</Button>
                          </DialogFooter>
                        </DialogContent>
                      </Dialog>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}