import React, { useEffect, useState } from "react";
import api from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import { BarChart, Bar, ResponsiveContainer, XAxis, YAxis, Tooltip, PieChart, Pie, Cell, LineChart, Line } from "recharts";

const COLORS = ["hsl(var(--chart-1))","hsl(var(--chart-2))","hsl(var(--chart-3))","hsl(var(--chart-4))","hsl(var(--chart-5))"];

export default function Analytics() {
  const [data, setData] = useState(null);
  useEffect(() => { api.get("/analytics/overview").then((r) => setData(r.data)); }, []);
  if (!data) return <div className="text-sm text-muted-foreground">Chargement…</div>;

  const k = data.kpis || {};
  const kpiRow = [
    ["Prospects trouvés", k.prospects_found], ["Qualifiés", k.qualified],
    ["Score moyen", k.avg_score], ["Messages préparés", k.messages_prepared],
    ["Messages envoyés", k.messages_sent], ["Réponses", k.replies],
    ["Rendez-vous", k.meetings], ["Taux de réponse", (k.response_rate || 0) + "%"],
  ];

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Analytics</h1>
        <p className="text-sm text-muted-foreground mt-1">Performance de vos campagnes et de vos agents.</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {kpiRow.map(([label, val]) => (
          <Card key={label}><CardContent className="p-4">
            <div className="text-xs text-muted-foreground">{label}</div>
            <div className="text-2xl font-semibold mt-1">{val ?? 0}</div>
          </CardContent></Card>
        ))}
      </div>

      <div className="grid lg:grid-cols-2 gap-4">
        <Card><CardContent className="p-6">
          <h3 className="font-semibold mb-4">Prospects par jour</h3>
          <ResponsiveContainer width="100%" height={220}>
            <LineChart data={data.by_day}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Line type="monotone" dataKey="value" stroke="hsl(var(--chart-1))" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </CardContent></Card>

        <Card><CardContent className="p-6">
          <h3 className="font-semibold mb-4">Top secteurs</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.by_industry}>
              <XAxis dataKey="name" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Bar dataKey="value" fill="hsl(var(--chart-2))" radius={[6,6,0,0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent></Card>

        <Card><CardContent className="p-6">
          <h3 className="font-semibold mb-4">Prospects par ville</h3>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={data.by_city} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="name" tick={{ fontSize: 11 }} width={100} />
              <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
              <Bar dataKey="value" fill="hsl(var(--chart-3))" radius={[0,6,6,0]} />
            </BarChart>
          </ResponsiveContainer>
        </CardContent></Card>

        <Card><CardContent className="p-6">
          <h3 className="font-semibold mb-4">Répartition par statut</h3>
          <ResponsiveContainer width="100%" height={220}>
            <PieChart>
              <Pie data={data.by_status} dataKey="value" nameKey="name" outerRadius={80} label={{ fontSize: 11 }}>
                {data.by_status.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
              </Pie>
              <Tooltip contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))" }} />
            </PieChart>
          </ResponsiveContainer>
        </CardContent></Card>
      </div>
    </div>
  );
}
