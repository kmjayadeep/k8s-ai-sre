{{/*
Expand the name of the chart.
*/}}
{{- define "k8s-ai-sre.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "k8s-ai-sre.fullname" -}}
{{- $name := include "k8s-ai-sre.name" . }}
{{- if .Values.namespace.create | not }}
{{- printf "%s" $name }}
{{- else }}
{{- printf "%s" $name }}
{{- end }}
{{- end }}

{{/*
The namespace for all RBAC resources, except the write Roles which go in their target namespaces.
*/}}
{{- define "k8s-ai-sre.namespace" -}}
{{- .Values.namespace.name }}
{{- end }}

{{/*
Common labels.
*/}}
{{- define "k8s-ai-sre.labels" -}}
app.kubernetes.io/name: {{ include "k8s-ai-sre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end }}

{{/*
Selector labels.
*/}}
{{- define "k8s-ai-sre.selectorLabels" -}}
app.kubernetes.io/name: {{ include "k8s-ai-sre.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Render WRITE_ALLOWED_NAMESPACES as a comma-separated string for the env var.
*/}}
{{- define "k8s-ai-sre.writeAllowedNamespaces" -}}
{{- $namespaces := .Values.writeAllowedNamespaces | default (list) -}}
{{- $joined := "" -}}
{{- range $i, $ns := $namespaces -}}
{{- if $i }}, {{ end -}}{{ $ns }}
{{- end }}
{{- end }}

{{/*
Determine which secret name to use.
*/}}
{{- define "k8s-ai-sre.secretName" -}}
{{- if .Values.existingSecret.name }}
{{- .Values.existingSecret.name }}
{{- else }}
{{- printf "%s-env" (include "k8s-ai-sre.fullname" .) }}
{{- end }}
{{- end }}
