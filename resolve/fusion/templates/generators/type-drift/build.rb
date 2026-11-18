#!/usr/bin/env ruby
# Rebuild the checked-in Fusion setting. No gems, fonts or Resolve API required.
# Native node/input names follow Resolve 21.1's Outline Repeat and Colorful Split.
require 'json'

def value(v)
  "Input { Value = #{v.is_a?(String) ? v.to_json : v}, }"
end

def expr(s)
  "Input { Expression = #{s.to_json}, }"
end

def wire(node, port = 'Output')
  "Input { SourceOp = #{node.to_json}, Source = #{port.to_json}, }"
end

def tool(name, kind, inputs, x, y, extra = '')
  <<~LUA
    #{name} = #{kind} {
      Inputs = {
    #{inputs.map { |key, val| "    #{key} = #{val}," }.join("\n")}
      },
      ViewInfo = OperatorInfo { Pos = { #{x}, #{y} } },
      #{extra}
    },
  LUA
end

published = []
def publish(list, node, port, label, page, group = nil)
  fields = ["SourceOp = #{node.to_json}", "Source = #{port.to_json}",
            "Name = #{label.to_json}", "Page = #{page.to_json}"]
  fields << "ControlGroup = #{group}" if group
  list << "Input#{list.length + 1} = InstanceInput { #{fields.join(', ')}, },"
end

publish(published, 'Phrase', 'StyledText', 'Text', 'Text')
publish(published, 'Phrase', 'Font', 'Font', 'Text', 1)
publish(published, 'Phrase', 'Style', 'Style', 'Text', 1)
publish(published, 'Phrase', 'Size', 'Text size', 'Text')
publish(published, 'Phrase', 'Thickness1', 'Outline thickness', 'Text')
publish(published, 'Canvas', 'RepeatSpacing', 'Repeat spacing', 'Text')
publish(published, 'Canvas', 'RowSpacing', 'Row spacing', 'Text')
publish(published, 'Tilt', 'ZRotation', 'Angle', 'Text')
%w[Red Green Blue].each do |channel|
  publish(published, 'Ink', "TopLeft#{channel}", 'Text color', 'Look', 2)
end
%w[Red Green Blue].each do |channel|
  publish(published, 'Canvas', "TopLeft#{channel}", 'Background', 'Look', 3)
end
publish(published, 'Grain', 'MasterStrength', 'Grain strength', 'Look')
publish(published, 'Grain', 'MasterXSize', 'Grain size', 'Look')
publish(published, 'Canvas', 'Speed', 'Speed (widths / second)', 'Motion')

# Indices run from bottom (-6) to top (+6), measured before the global tilt.
rates = {-6 => -1.15, -5 => 1.7, -4 => -0.85, -3 => 1.35,
         -2 => 0.7, -1 => -1.8, 0 => 0.2, 1 => 1.6,
         2 => -0.75, 3 => -1.4, 4 => 0.9, 5 => -1.65, 6 => 1.1}
([0] + (1..6).flat_map { |i| [i, -i] }).each do |i|
  id = i == 0 ? 'CenterRate' : "#{i > 0 ? 'Above' : 'Below'}#{i.abs}Rate"
  label = i == 0 ? 'Center multiplier' : "#{i > 0 ? 'Above' : 'Below'} #{i.abs} multiplier"
  publish(published, 'Canvas', id, label, 'Motion')
end

controls = []
canvas = {
  'UseFrameFormatSettings' => value(1),
  'TopLeftRed' => value(0), 'TopLeftGreen' => value(0),
  'TopLeftBlue' => value(0), 'TopLeftAlpha' => value(1)
}
numeric = lambda do |id, label, default, low, high|
  canvas[id] = value(default)
  controls << <<~LUA
    #{id} = {
      LINKID_DataType = "Number", INPID_InputControl = "SliderControl",
      LINKS_Name = #{label.to_json}, INP_Default = #{default},
      INP_MinScale = #{low}, INP_MaxScale = #{high},
      INP_MinAllowed = #{low}, INP_MaxAllowed = #{high},
      INP_Integer = false,
    },
  LUA
end
numeric.call('Speed', 'Speed (widths / second)', 0.08, 0, 0.5)
numeric.call('RepeatSpacing', 'Repeat spacing', 1.05, 0.35, 3)
numeric.call('RowSpacing', 'Row spacing', 0.095, 0.09, 0.2)
rates.each do |i, rate|
  id = i == 0 ? 'CenterRate' : "#{i > 0 ? 'Above' : 'Below'}#{i.abs}Rate"
  numeric.call(id, id, rate, -4, 4)
end

nodes = []
nodes << tool('Canvas', 'Background', canvas, 700, 200,
              "UserControls = ordered() {\n#{controls.join}\n},")
nodes << tool('Phrase', 'sText', {
  'Center' => 'Input { Value = { 0, 0 }, }',
  'StyledText' => value('ivanpotylitcyn.ru'),
  'Font' => value('JetBrains Mono'), 'Style' => value('ExtraBold'),
  'Size' => value(0.085), 'ElementShape1' => value(1),
  'Thickness1' => value(0.012),
  'VerticalJustificationNew' => value(3),
  'HorizontalJustificationNew' => value(3)
}, -800, 0)
nodes << tool('Copies', 'sDuplicate', {
  'Input' => wire('Phrase'), 'Copies' => value(12),
  'TimeOffset' => value(0), 'XOffset' => expr('Canvas.RepeatSpacing'),
  'YOffset' => value(0), 'AxisMode' => 'Input { Value = FuID { "Progressive" }, }'
}, -600, 0)

# Wrap by exactly the same distance as the duplicate spacing. A wrap replaces
# each visible copy with its identical neighbour; only far off-screen edges jump.
# Modulo via floor also handles negative rates and negative timeline times.
rates.each do |i, _|
  id = i == 0 ? 'CenterRate' : "#{i > 0 ? 'Above' : 'Below'}#{i.abs}Rate"
  phase = ((i * 0.317) % 1).round(6)
  distance = "((time-comp.RenderStart)/comp:GetPrefs(\"Comp.FrameFormat.Rate\")*Canvas.Speed*Canvas.#{id}+#{phase}*Canvas.RepeatSpacing)"
  wrapped = "#{distance}-floor(#{distance}/Canvas.RepeatSpacing)*Canvas.RepeatSpacing-6*Canvas.RepeatSpacing"
  nodes << tool("Row#{i + 6}", 'sTransform', {
    'Input' => wire('Copies'), 'XOffset' => expr(wrapped),
    'YOffset' => expr("#{i}*Canvas.RowSpacing")
  }, -350, -i * 55)
end
nodes << tool('Rows', 'sMerge', (0..12).to_h { |i| ["Input#{i + 1}", wire("Row#{i}")] }, -100, 0)
nodes << tool('Tilt', 'sTransform', {
  'Input' => wire('Rows'), 'ZRotation' => value(22),
  'XPivot' => value(0), 'YPivot' => value(0)
}, 100, 0)
nodes << tool('Letters', 'sRender', {
  'UseFrameFormatSettings' => value(1), 'Input' => wire('Tilt')
}, 300, 0)
nodes << tool('Ink', 'Background', {
  'UseFrameFormatSettings' => value(1), 'EffectMask' => wire('Letters'),
  'TopLeftRed' => value(0.16), 'TopLeftGreen' => value(0.16),
  'TopLeftBlue' => value(0.16), 'TopLeftAlpha' => value(1)
}, 500, 0)
nodes << tool('Composite', 'Merge', {
  'Background' => wire('Canvas'), 'Foreground' => wire('Ink')
}, 700, 0)
nodes << tool('Grain', 'FilmGrain', {
  'Input' => wire('Composite'), 'Monochrome' => value(1),
  'MasterStrength' => value(0.025), 'MasterXSize' => value(1.2),
  'MasterOffset' => expr('MasterStrength*0.32')
}, 900, 0)

setting = <<~LUA
  {
    Tools = ordered() {
      TypeDrift = GroupOperator {
        CtrlWZoom = false,
        Inputs = ordered() {
  #{published.join("\n")}
        },
        Outputs = {
          MainOutput1 = InstanceOutput { SourceOp = "Grain", Source = "Output", },
        },
        ViewInfo = GroupInfo { Pos = { 0, 0 } },
        Tools = ordered() {
  #{nodes.join("\n")}
        },
      },
    },
    ActiveTool = "TypeDrift",
  }
LUA
File.write(File.join(__dir__, 'Type Drift.setting'), setting)
puts 'Built Type Drift.setting'
